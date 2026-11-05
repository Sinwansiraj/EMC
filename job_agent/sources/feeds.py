"""Remotive public API, job-alert emails (LinkedIn / Naukri / Indeed), and manual imports.

Job sites like LinkedIn and Naukri forbid scraping, so the agent never crawls them. Instead it
reads the alert emails those sites already send you (read-only IMAP, or .eml files you drop into
private/alerts/), and you apply to those jobs yourself from a prepared pack.
"""
from __future__ import annotations

import csv
import email
import imaplib
import os
import re
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from pathlib import Path

from .base import Http, Job, html_to_text, is_remote, iso, parse_deadline, parse_salary_inr

# ---------------------------------------------------------------- platform detection
PLATFORM_PATTERNS = [
    ("greenhouse", r"greenhouse\.io"),
    ("lever", r"jobs\.lever\.co"),
    ("ashby", r"ashbyhq\.com"),
    ("workable", r"workable\.com"),
    ("linkedin", r"linkedin\.com"),
    ("naukri", r"naukri\.com"),
    ("indeed", r"indeed\.(com|co\.in)"),
    ("foundit", r"foundit\.in|monsterindia"),
    ("instahyre", r"instahyre\.com"),
    ("remotive", r"remotive\.com"),
    ("remoteok", r"remoteok\.(com|io)"),
    ("weworkremotely", r"weworkremotely\.com"),
    ("himalayas", r"himalayas\.app"),
]


def detect_platform(url: str) -> str:
    for name, pat in PLATFORM_PATTERNS:
        if re.search(pat, url or "", re.I):
            return name
    return "other"


# ---------------------------------------------------------------- Remotive
REMOTIVE_OK_REGIONS = ("india", "worldwide", "anywhere", "asia", "apac", "global")


def remotive(http: Http, queries: list[str], remote_kw: list[str]) -> list[Job]:
    """Remotive asks API users to keep calls low and link back to the posting; we store its URL."""
    out, seen = [], set()
    for q in queries:
        r = http.get("https://remotive.com/api/remote-jobs", params={"search": q, "limit": 100})
        if not r.ok:
            continue
        for j in r.json().get("jobs", []):
            if j["id"] in seen:
                continue
            seen.add(j["id"])
            region = (j.get("candidate_required_location") or "").lower()
            if region and not any(k in region for k in REMOTIVE_OK_REGIONS):
                continue  # e.g. "USA only" - not eligible from India
            desc = html_to_text(j.get("description"))
            smin, smax = parse_salary_inr(j.get("salary") or "")
            out.append(Job(
                source="remotive", platform="remotive", external_id=str(j["id"]), url=j.get("url", ""),
                apply_url=j.get("url", ""), title=j.get("title", ""), company=j.get("company_name", ""),
                location=j.get("candidate_required_location") or "Remote", description=desc,
                remote=True, salary_min=smin, salary_max=smax, posted_at=iso(j.get("publication_date")),
                deadline=parse_deadline(desc),
            ))
    return out


# ---------------------------------------------------------------- alert emails
LINK_PATTERNS = {
    "linkedin": re.compile(r'href="(https?://(?:www\.)?linkedin\.com/(?:comm/)?jobs/view/(\d+)[^"]*)"[^>]*>(.*?)</a>', re.S | re.I),
    "naukri": re.compile(r'href="(https?://(?:www\.)?naukri\.com/job-listings-[^"]*?-(\d{6,})[^"]*)"[^>]*>(.*?)</a>', re.S | re.I),
    "indeed": re.compile(r'href="(https?://(?:[a-z]+\.)?indeed\.(?:com|co\.in)/(?:rc/clk|viewjob|pagead/clk)[^"]*?jk=([a-f0-9]+)[^"]*)"[^>]*>(.*?)</a>', re.S | re.I),
}
CANONICAL = {
    "linkedin": "https://www.linkedin.com/jobs/view/{id}/",
    "naukri": None,  # keep original URL minus tracking params
    "indeed": "https://in.indeed.com/viewjob?jk={id}",
}
NOISE = re.compile(r"(?i)^(view job|apply|apply now|see all jobs|easy apply|save|new|promoted|actively recruiting|\d+ (applicants|connections?).*)$")


def _decode(s) -> str:
    try:
        return str(make_header(decode_header(s or "")))
    except Exception:  # noqa: BLE001
        return s or ""


def _html_of(msg: email.message.Message) -> str:
    parts = []
    for part in msg.walk():
        if part.get_content_type() in ("text/html", "text/plain") and not part.get_filename():
            payload = part.get_payload(decode=True) or b""
            parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
    return "\n".join(parts)


def parse_alert_email(raw_html: str, remote_kw: list[str]) -> list[Job]:
    """Pull job links + title/company/location lines out of an alert email body."""
    jobs: dict[str, Job] = {}
    for platform, pat in LINK_PATTERNS.items():
        for m in pat.finditer(raw_html):
            url, jid, anchor = m.group(1), m.group(2), html_to_text(m.group(3)).strip()
            key = f"{platform}:{jid}"
            texts = [t.strip() for t in anchor.split("\n") if t.strip() and not NOISE.match(t.strip())]
            if key not in jobs:
                canon = CANONICAL[platform].format(id=jid) if CANONICAL[platform] else url.split("?")[0]
                jobs[key] = Job(source=f"{platform}_alert", platform=platform, external_id=jid,
                                url=canon, apply_url=canon, title="", company="", partial=True)
            j = jobs[key]
            for t in texts:
                if not j.title and len(t) > 3:
                    j.title = t
                elif t != j.title and "·" in t and not j.company:
                    company, _, loc = t.partition("·")
                    j.company, j.location = company.strip(), loc.strip()
                elif t != j.title and not j.company and len(t) < 80:
                    j.company = t
                elif t != j.title and t != j.company and not j.location and len(t) < 80:
                    j.location = t
    # Fall back to plain-text lines after the title when anchors held only the title.
    text = html_to_text(raw_html)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for j in jobs.values():
        if j.title and (not j.company or not j.location):
            try:
                i = lines.index(j.title)
            except ValueError:
                continue
            nxt = [l for l in lines[i + 1:i + 4] if not NOISE.match(l)]
            if nxt and not j.company:
                if "·" in nxt[0]:
                    c, _, loc = nxt[0].partition("·")
                    j.company, j.location = c.strip(), j.location or loc.strip()
                else:
                    j.company = nxt[0]
                    if len(nxt) > 1 and not j.location:
                        j.location = nxt[1]
        j.remote = is_remote(j.location, "", remote_kw)
        j.description = " ".join(filter(None, [j.title, j.company, j.location]))
    return [j for j in jobs.values() if j.title and j.company]


def email_alerts_imap(cfg: dict, remote_kw: list[str]) -> list[Job]:
    """Read-only IMAP. Needs IMAP_USER and IMAP_APP_PASSWORD (a Gmail app password) in private/.env."""
    user, pw = os.environ.get("IMAP_USER"), os.environ.get("IMAP_APP_PASSWORD")
    if not (user and pw):
        raise RuntimeError("IMAP_USER / IMAP_APP_PASSWORD not set in private/.env")
    since = (datetime.now() - timedelta(days=cfg.get("lookback_days", 3))).strftime("%d-%b-%Y")
    out: list[Job] = []
    with imaplib.IMAP4_SSL(cfg.get("imap_host", "imap.gmail.com")) as M:
        M.login(user, pw)
        M.select(cfg.get("folder", "INBOX"), readonly=True)   # never marks mail read or changes it
        for sender in cfg.get("senders", []):
            typ, data = M.search(None, f'(SINCE {since} FROM "{sender}")')
            if typ != "OK":
                continue
            for num in data[0].split():
                typ, msg_data = M.fetch(num, "(BODY.PEEK[])")
                if typ != "OK" or not msg_data or not msg_data[0]:
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                out.extend(parse_alert_email(_html_of(msg), remote_kw))
    return out


def email_alerts_folder(folder: Path, remote_kw: list[str]) -> list[Job]:
    out: list[Job] = []
    for p in sorted(folder.glob("*.eml")):
        msg = email.message_from_bytes(p.read_bytes())
        out.extend(parse_alert_email(_html_of(msg), remote_kw))
    return out


# ---------------------------------------------------------------- manual CSV
def manual_csv(path: Path, remote_kw: list[str]) -> list[Job]:
    """CSV columns: url,title,company,location,description (description optional but improves scoring)."""
    if not path.exists():
        return []
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            url = (row.get("url") or "").strip()
            if not url or not row.get("title") or not row.get("company"):
                continue
            desc = row.get("description", "") or ""
            smin, smax = parse_salary_inr(desc)
            out.append(Job(
                source="manual", platform=detect_platform(url), url=url, apply_url=url,
                title=row["title"].strip(), company=row["company"].strip(),
                location=(row.get("location") or "").strip(), description=desc,
                remote=is_remote(row.get("location", ""), desc, remote_kw),
                salary_min=smin, salary_max=smax, deadline=parse_deadline(desc), partial=not desc,
            ))
    return out
