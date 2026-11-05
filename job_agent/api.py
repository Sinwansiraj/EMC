"""JSON read-models and action wrappers for the web UI.

This module is the boundary the frontend sits on. It reuses the same SQL and the
same pipeline functions the CLI uses (discover/score/prepare/apply, tracker) but
returns plain dicts/lists instead of preformatted text, so the CLI stays intact.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .db import DB
from . import tracker

# Statuses that count as "the application left the building" (mirrors tracker).
SUBMITTED_LIKE = tracker.SUBMITTED_LIKE
REVIEW_STATUSES = ("prepared", "awaiting_approval", "needs_human")


def _loads(blob, default):
    try:
        return json.loads(blob) if blob else default
    except (ValueError, TypeError):
        return default


def _rows(rows) -> list[dict]:
    return [dict(r) for r in rows]


# --------------------------------------------------------------- dashboard
def dashboard(db: DB) -> dict:
    apps_by_status = _rows(db.q(
        "SELECT status, COUNT(*) c FROM applications GROUP BY status ORDER BY c DESC"))
    jobs_by_status = _rows(db.q(
        "SELECT status, COUNT(*) c FROM jobs GROUP BY status ORDER BY c DESC"))

    ph = ",".join("?" * len(SUBMITTED_LIKE))
    performance = _rows(db.q(
        f"""SELECT j.role_family family, COUNT(*) applied,
                   SUM(a.status IN ('interview','offer')) interviews,
                   SUM(a.status='rejected') rejected,
                   ROUND(AVG(j.score),1) avg_score
            FROM applications a JOIN jobs j ON j.id=a.job_id
            WHERE a.status IN ({ph})
            GROUP BY family ORDER BY interviews*1.0/applied DESC, applied DESC""",
        SUBMITTED_LIKE))
    for r in performance:
        n = r["applied"] or 1
        r["interview_rate"] = round(100 * (r["interviews"] or 0) / n)

    by_source = _rows(db.q(
        f"""SELECT j.source, COUNT(*) applied,
                   SUM(a.status IN ('interview','offer')) interviews
            FROM applications a JOIN jobs j ON j.id=a.job_id
            WHERE a.status IN ({ph}) GROUP BY j.source ORDER BY applied DESC""",
        SUBMITTED_LIKE))

    today = datetime.now().date().isoformat()
    follow_ups = _rows(db.q(
        """SELECT a.id, j.title, j.company, a.follow_up_on
           FROM applications a JOIN jobs j ON j.id=a.job_id
           WHERE a.follow_up_on IS NOT NULL AND a.follow_up_on <= ?
             AND a.status IN ('submitted','submitted_unverified')
           ORDER BY a.follow_up_on""", (today,)))

    waiting = _rows(db.q(
        """SELECT a.id, j.title, j.company, a.status, a.selection_reason,
                  substr(a.notes,1,120) notes
           FROM applications a JOIN jobs j ON j.id=a.job_id
           WHERE a.status IN ('prepared','awaiting_approval','needs_human')
           ORDER BY j.score DESC"""))

    unverified = db.one(
        "SELECT COUNT(*) c FROM applications WHERE status='submitted_unverified'")["c"]

    return {
        "apps_by_status": apps_by_status,
        "jobs_by_status": jobs_by_status,
        "submitted_today": db.submitted_today(),
        "performance": performance,
        "by_source": by_source,
        "follow_ups": follow_ups,
        "waiting_on_you": waiting,
        "unverified": unverified,
    }


# --------------------------------------------------------------- jobs
def jobs(db: DB, status: str = "scored", limit: int = 50) -> list[dict]:
    rows = _rows(db.q(
        """SELECT id, score, role_family, title, company, location, platform,
                  remote, filter_reason, deadline, salary_min, salary_max,
                  url, apply_url, score_detail, missing, status, first_seen_at
           FROM jobs WHERE status=? ORDER BY score DESC, first_seen_at DESC LIMIT ?""",
        (status, limit)))
    for r in rows:
        r["score_detail"] = _loads(r.pop("score_detail"), {})
        r["missing"] = _loads(r.pop("missing"), [])
    return rows


def job_status_counts(db: DB) -> dict:
    return {r["status"]: r["c"] for r in db.q(
        "SELECT status, COUNT(*) c FROM jobs GROUP BY status")}


# --------------------------------------------------------------- applications
def applications(db: DB, status: str | None = None, limit: int = 100) -> list[dict]:
    where, args = "", []
    if status == "review":
        ph = ",".join("?" * len(REVIEW_STATUSES))
        where = f"WHERE a.status IN ({ph})"
        args = list(REVIEW_STATUSES)
    elif status:
        where, args = "WHERE a.status=?", [status]
    rows = _rows(db.q(
        f"""SELECT a.id, a.job_id, a.status, a.resume_version, a.selection_reason,
                   a.approval, a.submitted_at, a.follow_up_on, a.verification,
                   j.title, j.company, j.platform, j.score, j.url
            FROM applications a JOIN jobs j ON j.id=a.job_id
            {where} ORDER BY j.score DESC, a.id DESC LIMIT ?""",
        (*args, limit)))
    return rows


def application_detail(db: DB, app_id: int) -> dict | None:
    app = db.one("SELECT * FROM applications WHERE id=?", (app_id,))
    if not app:
        return None
    app = dict(app)
    job = db.one("SELECT * FROM jobs WHERE id=?", (app["job_id"],))
    job = dict(job) if job else {}

    answers = []
    for label, a in _loads(app.get("answers"), {}).items():
        answers.append({
            "label": label,
            "value": a.get("value"),
            "confidence": a.get("confidence"),
            "source": a.get("source"),
            "note": a.get("note"),
        })

    events = _rows(db.q(
        """SELECT at, event, detail FROM audit
           WHERE app_id=? OR (job_id=? AND app_id IS NULL) ORDER BY id""",
        (app_id, app["job_id"])))

    # Which document files exist on disk (names only; served via /files).
    docs = {}
    for key in ("resume_path", "cover_path"):
        p = app.get(key)
        docs[key] = {"path": p, "exists": bool(p and Path(p).exists())}

    app["answers"] = None  # drop the raw blob from the payload
    job["score_detail"] = _loads(job.get("score_detail"), {})
    job["missing"] = _loads(job.get("missing"), [])
    return {"application": app, "job": job, "answers": answers,
            "events": events, "documents": docs}


# --------------------------------------------------------------- actions
def approve(db: DB, app_id: int) -> None:
    db.update_app(app_id, status="approved", approval="approved_by_user_pending_fill")
    db.audit("approved_in_review", None, app_id=app_id)


def reject(db: DB, app_id: int) -> None:
    db.update_app(app_id, status="withdrawn", approval="declined_by_user")
    db.audit("declined_by_user", None, app_id=app_id)


def set_outcome(db: DB, app_id: int, outcome: str, note: str = "") -> None:
    tracker.set_status(db, app_id, outcome, note)  # validates outcome, raises SystemExit
