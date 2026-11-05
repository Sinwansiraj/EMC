"""Pick the best-ranked jobs, enforce duplicate/limit rules, and build an application pack for each."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from .config import PRIVATE
from .db import DB, now
from .discover import norm_company
from .privacy import ensure_private_dir
from .tailor import prepare_documents

ACTIVE = ("prepared", "awaiting_approval", "approved", "submitted", "submitted_unverified",
          "interview", "offer", "needs_human")


def duplicate_reason(db: DB, job: dict, cfg: dict) -> str | None:
    lim = cfg["limits"]
    company = norm_company(job["company"])
    since_dup = (datetime.now(timezone.utc) - timedelta(days=lim["duplicate_window_days"])).isoformat()
    since_30 = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = db.q(
        f"""SELECT j.fingerprint, a.created_at, a.status FROM applications a JOIN jobs j ON j.id=a.job_id
            WHERE a.status IN ({','.join('?' * len(ACTIVE))}) AND a.created_at >= ?""", (*ACTIVE, since_dup))
    same_company_30 = 0
    for r in rows:
        comp, _, title = r["fingerprint"].partition("|")
        if comp != company:
            continue
        if r["fingerprint"] == job["fingerprint"]:
            return "already applied to this role"
        if r["created_at"] >= since_30:
            same_company_30 += 1
    if same_company_30 >= lim["per_company_per_30_days"]:
        return f"already {same_company_30} applications to {job['company']} in 30 days"
    return None


def selection_reason(job: dict) -> str:
    d = json.loads(job["score_detail"] or "{}")
    miss = json.loads(job["missing"] or "[]")
    parts = [f"score {job['score']:.0f}/100 as {job['role_family']}",
             f"role {d.get('role')}/25, skills {d.get('skills')}/40, experience {d.get('experience')}/20, "
             f"location {d.get('location')}/10, salary {d.get('salary')}/5"]
    if d.get("skills_matched"):
        parts.append("matched: " + ", ".join(d["skills_matched"]))
    if miss:
        parts.append("gaps: " + "; ".join(miss))
    return " | ".join(parts)


def run(db: DB, profile: dict, cfg: dict, limit: int | None = None) -> dict:
    cap = cfg["limits"]["daily_application_cap"]
    room = max(0, cap - db.submitted_today())
    queued = db.one("SELECT COUNT(*) c FROM applications WHERE status IN ('prepared','awaiting_approval','approved')")["c"]
    room = max(0, room - queued)
    if limit is not None:
        room = min(room, limit)
    stats = {"prepared": 0, "skipped_duplicate": 0, "below_threshold": 0, "room": room}
    if room == 0:
        return stats
    today = datetime.now().date().isoformat()
    jobs = db.q("""SELECT * FROM jobs WHERE status='scored'
                   AND (deadline IS NULL OR deadline >= ?) ORDER BY score DESC, first_seen_at DESC""", (today,))
    base = ensure_private_dir(PRIVATE / "applications")
    for r in jobs:
        if stats["prepared"] >= room:
            break
        job = dict(r)
        if job["score"] < cfg["filters"]["min_match_score"]:
            stats["below_threshold"] += 1
            continue
        dup = duplicate_reason(db, job, cfg)
        if dup:
            db.x("UPDATE jobs SET status='duplicate', filter_reason=? WHERE id=?", (dup, job["id"]))
            db.audit("skipped_duplicate", dup, job_id=job["id"])
            stats["skipped_duplicate"] += 1
            continue
        docs = prepare_documents(job, profile, cfg, base / str(job["id"]))
        reason = selection_reason(job)
        ts = now()
        app_id = db.x(
            """INSERT INTO applications(job_id, status, resume_path, resume_version, cover_path, answers,
               selection_reason, approval, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (job["id"], "prepared", docs["resume_path"], docs["resume_version"], docs["cover_path"],
             json.dumps({}), reason, "none", ts, ts))
        db.x("UPDATE jobs SET status='prepared' WHERE id=?", (job["id"],))
        db.audit("application_prepared", {
            "why_selected": reason, "resume_version": docs["resume_version"], "projects": docs["projects"],
            "text_source": docs["text_source"], "guard_violations": docs["guard_violations"],
        }, job_id=job["id"], app_id=app_id)
        if docs["guard_violations"]:
            db.update_app(app_id, status="needs_human",
                          notes="invention guard: " + "; ".join(docs["guard_violations"]))
        stats["prepared"] += 1
    return stats
