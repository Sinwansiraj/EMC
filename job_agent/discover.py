"""Collect jobs from every enabled source, de-duplicate, and store them."""
from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher

from .config import ROOT, load_companies
from .db import DB, now
from .sources import ats, feeds, jobspipe, remote_boards
from .sources.base import Http, Job

log = logging.getLogger(__name__)

_COMPANY_SUFFIX = re.compile(
    r"\b(private|pvt|limited|ltd|llp|inc|incorporated|corp|corporation|co|company|gmbh|plc|technologies|technology|"
    r"solutions|software|labs|india|global|group)\b\.?", re.I)
_TITLE_NOISE = re.compile(r"\(.*?\)|\[.*?\]|\b(remote|hybrid|onsite|on-site|wfh|urgent|hiring|immediate joiner[s]?)\b|[-–|,/]+", re.I)


def norm_company(c: str) -> str:
    c = _COMPANY_SUFFIX.sub(" ", (c or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", c).strip()


def norm_title(t: str) -> str:
    t = _TITLE_NOISE.sub(" ", (t or "").lower())
    t = t.replace("sr.", "senior").replace("jr.", "junior")
    return re.sub(r"[^a-z0-9+#]+", " ", t).strip()


def fingerprint(job: Job) -> str:
    # Location deliberately excluded: the same role posted for 3 cities is one application.
    return f"{norm_company(job.company)}|{norm_title(job.title)}"


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def store(db: DB, jobs: list[Job]) -> dict:
    stats = {"seen": 0, "new": 0, "duplicates_merged": 0}
    ts = now()
    by_company: dict[str, list] = {}
    for row in db.q("SELECT id, fingerprint FROM jobs"):
        comp, _, title = row["fingerprint"].partition("|")
        by_company.setdefault(comp, []).append((row["id"], title))

    for j in jobs:
        stats["seen"] += 1
        if not j.title or not j.company or not j.url:
            continue
        fp = fingerprint(j)
        comp, _, title = fp.partition("|")
        match_id = None
        for jid, t in by_company.get(comp, []):
            if t == title or _similar(t, title) >= 0.92:
                match_id = jid
                break
        if match_id:
            row = db.one("SELECT url, also_seen_at, description, status FROM jobs WHERE id=?", (match_id,))
            also = set(json.loads(row["also_seen_at"] or "[]"))
            if j.url != row["url"]:
                also.add(j.url)
            upd = {"last_seen_at": ts, "also_seen_at": json.dumps(sorted(also))}
            # Upgrade a thin alert snippet with a full description from a better source.
            old_desc = row["description"] or ""
            if (len(old_desc) < 200 and len(j.description) > len(old_desc)
                    and row["status"] in ("discovered", "scored", "filtered")):
                upd.update(description=j.description, apply_url=j.apply_url, platform=j.platform,
                           status="discovered", score=None)
            cols = ", ".join(f"{k}=?" for k in upd)
            db.x(f"UPDATE jobs SET {cols} WHERE id=?", (*upd.values(), match_id))
            stats["duplicates_merged"] += 1
            continue
        jid = db.x(
            """INSERT INTO jobs(fingerprint, source, platform, external_id, url, apply_url, title, company,
               location, remote, description, salary_min, salary_max, posted_at, deadline, first_seen_at, last_seen_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fp, j.source, j.platform, j.external_id, j.url, j.apply_url or j.url, j.title, j.company,
             j.location, int(j.remote), j.description, j.salary_min, j.salary_max, j.posted_at, j.deadline, ts, ts))
        by_company.setdefault(comp, []).append((jid, title))
        db.audit("job_discovered", {"source": j.source, "url": j.url, "title": j.title, "company": j.company}, job_id=jid)
        stats["new"] += 1
    return stats


def run(db: DB, cfg: dict) -> dict:
    http = Http()
    remote_kw = cfg["search"]["locations"]["remote_keywords"]
    src = cfg["sources"]
    jobs: list[Job] = []
    errors: list[str] = []

    got, errs = ats.fetch_all(http, load_companies(cfg), remote_kw)
    jobs += got
    errors += errs

    if src.get("remotive", {}).get("enabled"):
        try:
            jobs += feeds.remotive(http, src["remotive"]["queries"], remote_kw)
        except Exception as e:  # noqa: BLE001
            errors.append(f"remotive: {e}")

    rb = src.get("remote_boards", {})
    if rb.get("remoteok", {}).get("enabled"):
        try:
            jobs += remote_boards.remoteok(http, rb["remoteok"])
        except Exception as e:  # noqa: BLE001
            errors.append(f"remoteok: {e}")
    if rb.get("weworkremotely", {}).get("enabled"):
        try:
            got, errs = remote_boards.weworkremotely(http, rb["weworkremotely"])
            jobs += got
            errors += errs
        except Exception as e:  # noqa: BLE001
            errors.append(f"weworkremotely: {e}")
    if rb.get("himalayas", {}).get("enabled"):
        try:
            got, errs = remote_boards.himalayas(http, rb["himalayas"])
            jobs += got
            errors += errs
        except Exception as e:  # noqa: BLE001
            errors.append(f"himalayas: {e}")

    jp_cfg = src.get("jobspipe", {})
    jp_stats = {}
    if jp_cfg.get("enabled"):
        try:
            got, errs, jp_stats = jobspipe.fetch(http, db, cfg, jp_cfg)
            jobs += got
            errors += errs
        except Exception as e:  # noqa: BLE001
            errors.append(f"jobspipe: {e}")

    if src.get("email_alerts", {}).get("enabled"):
        try:
            jobs += feeds.email_alerts_imap(src["email_alerts"], remote_kw)
        except Exception as e:  # noqa: BLE001
            errors.append(f"email alerts: {e}")
    alerts_dir = ROOT / "private" / "alerts"
    if alerts_dir.exists():
        jobs += feeds.email_alerts_folder(alerts_dir, remote_kw)

    jobs += feeds.manual_csv(ROOT / src["manual_import_file"], remote_kw)

    stats = store(db, jobs)
    stats["errors"] = errors
    if jp_stats:
        stats["jobspipe"] = jp_stats
    db.set_meta("last_discover_at", now())
    db.audit("discover_run", stats)
    return stats
