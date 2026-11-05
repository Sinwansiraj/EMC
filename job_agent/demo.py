"""Seed the local DB with demo jobs/applications for the public showcase.

Safe, synthetic data only — no real companies' application forms are touched.
Running it replaces any existing jobs/applications/audit rows, so use it on a
showcase database, not one with a real job hunt in progress.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from .db import DB, now

TODAY = datetime.now(timezone.utc)


def _iso(days: int = 0) -> str:
    return (TODAY + timedelta(days=days)).isoformat(timespec="seconds")


# (title, company, location, remote, role_family, score, status, filter_reason, missing, salary)
JOBS = [
    ("Data Analyst", "Northwind Analytics", "Bengaluru, IN", 1, "data-analyst", 91.0, "prepared", None, [], (900000, 1300000)),
    ("Machine Learning Engineer", "Helios AI", "Remote", 1, "ml-engineer", 88.0, "prepared", None, ["AWS SageMaker"], (1400000, 2000000)),
    ("Data Scientist", "Meridian Labs", "Hyderabad, IN", 0, "data-scientist", 84.5, "applied", None, [], (1200000, 1800000)),
    ("Python Backend Developer", "Zeta Commerce", "Remote", 1, "backend", 79.0, "applied", None, ["Kafka"], (1000000, 1500000)),
    ("Business Intelligence Analyst", "Clearwater Retail", "Pune, IN", 0, "data-analyst", 76.0, "scored", None, ["Power BI"], (700000, 1000000)),
    ("AI Product Analyst", "Lumen Health", "Remote", 1, "data-analyst", 72.5, "scored", None, ["Healthcare domain"], (900000, 1200000)),
    ("Senior Staff ML Scientist", "Helios AI", "San Francisco, US", 0, "ml-engineer", 58.0, "filtered", "needs 8+ yrs and onsite US", ["8+ years", "US work auth"], (None, None)),
    ("Marketing Data Coordinator", "Brightside Media", "Bengaluru, IN", 0, "data-analyst", 41.0, "filtered", "below score threshold", ["degree mismatch"], (400000, 550000)),
]

# (job_index, app_status, resume_version, approval, selection_reason, submitted_days_ago, follow_up_days, verification, notes)
APPS = [
    (0, "awaiting_approval", "data-analyst-v3", "pending",
     "Strong overlap: SQL, Python, dashboarding; remote; salary in range.", None, None, None, ""),
    (1, "awaiting_approval", "ml-engineer-v2", "pending",
     "Core ML stack matches; remote; one gap (SageMaker) flagged for review.", None, None,
     None, "Cover letter mentions transfer-learning project."),
    (2, "interview", "data-scientist-v1", "approved_by_user",
     "Top match on modeling + stats; applied via official Greenhouse board.", -12, None,
     "confirmation page captured", "HR screen scheduled."),
    (3, "submitted", "backend-v2", "approved_by_user",
     "Good Python/API fit; Kafka listed as nice-to-have.", -5, 2,
     "confirmation email id #A-20481", ""),
    (4, "needs_human", "data-analyst-v3", "none",
     "Match is solid but the form has a CAPTCHA the agent will not solve.", None, None,
     None, "CAPTCHA on final step — submit manually."),
]


def run(db: DB) -> dict:
    con = db.con
    con.execute("DELETE FROM audit")
    con.execute("DELETE FROM applications")
    con.execute("DELETE FROM jobs")
    con.commit()

    job_ids = []
    for i, (title, company, loc, remote, fam, score, status, filt, missing, sal) in enumerate(JOBS):
        fp = f"{company.lower()}|{title.lower()}|{i}"
        url = f"https://example.com/jobs/{i}-{title.lower().replace(' ', '-')}"
        detail = {"skills": round(score * 0.4, 1), "seniority": round(score * 0.3, 1),
                  "location": round(score * 0.3, 1)}
        jid = db.x(
            """INSERT INTO jobs(fingerprint, source, platform, external_id, url, apply_url,
                 title, company, location, remote, description, salary_min, salary_max,
                 posted_at, deadline, first_seen_at, last_seen_at, also_seen_at,
                 role_family, score, score_detail, missing, filter_reason, status)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fp, "greenhouse", "greenhouse", f"gh-{i}", url, url, title, company, loc, remote,
             f"{title} at {company}. Demo posting for the showcase.", sal[0], sal[1],
             _iso(-20 + i), _iso(25) if i % 3 == 0 else None, _iso(-20 + i), _iso(-1),
             "[]", fam, score, json.dumps(detail), json.dumps(missing), filt, status))
        job_ids.append(jid)
        db.audit("discovered", {"source": "greenhouse"}, job_id=jid)
        db.audit("scored", {"score": score}, job_id=jid)

    n_apps = 0
    for (ji, status, resume, approval, reason, sub_days, fu_days, verif, notes) in APPS:
        jid = job_ids[ji]
        answers = {
            "Full name": {"value": "Mohammed Sinwan", "confidence": "exact", "source": "profile"},
            "Years of experience": {"value": "4", "confidence": "exact", "source": "profile"},
            "Expected monthly salary (INR)": {"value": "95,000", "confidence": "derived",
                                              "source": "annual CTC / 12"},
            "Are you willing to relocate?": {"value": "Yes", "confidence": "exact", "source": "profile"},
            "Government ID number": {"value": "", "confidence": "unknown",
                                     "source": "never auto-filled", "note": "sensitive"},
        }
        aid = db.x(
            """INSERT INTO applications(job_id, status, resume_path, resume_version, cover_path,
                 answers, selection_reason, approval, approved_at, submitted_at, verification,
                 follow_up_on, notes, created_at, updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (jid, status, None, resume, None, json.dumps(answers), reason, approval,
             _iso(sub_days) if approval == "approved_by_user" else None,
             _iso(sub_days) if sub_days is not None else None, verif,
             (TODAY + timedelta(days=fu_days)).date().isoformat() if fu_days else None,
             notes, _iso(-15 + ji), _iso(-1)))
        db.audit("prepared", {"resume_version": resume}, job_id=jid, app_id=aid)
        if approval == "approved_by_user":
            db.audit("approved_by_user", None, job_id=jid, app_id=aid)
        if status in ("submitted", "interview"):
            db.audit("submitted", {"verification": verif}, job_id=jid, app_id=aid)
        if status == "interview":
            db.audit("status_changed", {"to": "interview"}, job_id=jid, app_id=aid)
        n_apps += 1

    return {"jobs": len(job_ids), "applications": n_apps}
