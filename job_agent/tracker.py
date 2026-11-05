"""Status updates, follow-ups, progress summary, CSV export and the audit trail view."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .db import DB, now

OUTCOMES = ("interview", "offer", "rejected", "withdrawn", "no_response", "submitted")
SUBMITTED_LIKE = ("submitted", "submitted_unverified", "interview", "offer", "rejected", "no_response")


def set_status(db: DB, app_id: int, status: str, note: str = "") -> None:
    if status not in OUTCOMES:
        raise SystemExit(f"status must be one of {', '.join(OUTCOMES)}")
    app = db.one("SELECT * FROM applications WHERE id=?", (app_id,))
    if not app:
        raise SystemExit(f"no application {app_id}")
    fields = {"status": status}
    if note:
        fields["notes"] = ((app["notes"] or "") + f"\n{now()[:10]}: {note}").strip()
    if status == "submitted" and not app["submitted_at"]:
        fields.update(submitted_at=now(), approval="approved_by_user", verification="marked by user")
    if status == "interview":
        fields["follow_up_on"] = None
    db.update_app(app_id, **fields)
    db.audit("status_changed", {"from": app["status"], "to": status, "note": note}, job_id=app["job_id"], app_id=app_id)


def sweep_no_response(db: DB, cfg: dict) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=cfg["tracking"]["mark_no_response_after_days"])).isoformat()
    rows = db.q("SELECT id, job_id FROM applications WHERE status IN ('submitted','submitted_unverified') AND submitted_at < ?",
                (cutoff,))
    for r in rows:
        db.update_app(r["id"], status="no_response")
        db.audit("status_changed", {"to": "no_response", "auto": True}, job_id=r["job_id"], app_id=r["id"])
    return len(rows)


def summary(db: DB) -> str:
    lines = []
    st = db.q("SELECT status, COUNT(*) c FROM applications GROUP BY status ORDER BY c DESC")
    lines.append("APPLICATIONS BY STATUS")
    lines += [f"  {r['status']:22} {r['c']}" for r in st] or ["  (none yet)"]

    jobs = db.q("SELECT status, COUNT(*) c FROM jobs GROUP BY status ORDER BY c DESC")
    lines.append("\nJOBS FOUND BY STATUS")
    lines += [f"  {r['status']:22} {r['c']}" for r in jobs] or ["  (none yet)"]

    lines.append(f"\nSubmitted today: {db.submitted_today()}")

    ph = ",".join("?" * len(SUBMITTED_LIKE))
    perf = db.q(f"""SELECT j.role_family fam, COUNT(*) n,
                    SUM(a.status IN ('interview','offer')) pos, SUM(a.status='rejected') rej,
                    ROUND(AVG(j.score),1) avg_score
                    FROM applications a JOIN jobs j ON j.id=a.job_id
                    WHERE a.status IN ({ph}) GROUP BY fam ORDER BY pos*1.0/n DESC, n DESC""", SUBMITTED_LIKE)
    lines.append("\nWHAT'S WORKING (by job type)")
    lines.append(f"  {'role family':24}{'applied':>8}{'interviews':>12}{'rejected':>10}{'rate':>8}{'avg score':>11}")
    for r in perf:
        rate = f"{100 * (r['pos'] or 0) / r['n']:.0f}%"
        lines.append(f"  {str(r['fam']):24}{r['n']:>8}{r['pos'] or 0:>12}{r['rej'] or 0:>10}{rate:>8}{r['avg_score']:>11}")
    if not perf:
        lines.append("  (no submitted applications yet)")

    src = db.q(f"""SELECT j.source, COUNT(*) n, SUM(a.status IN ('interview','offer')) pos
                   FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.status IN ({ph})
                   GROUP BY j.source ORDER BY n DESC""", SUBMITTED_LIKE)
    if src:
        lines.append("\nBY SOURCE")
        lines += [f"  {r['source']:24}{r['n']:>8} applied, {r['pos'] or 0} interviews" for r in src]

    rv = db.q(f"""SELECT a.resume_version v, COUNT(*) n, SUM(a.status IN ('interview','offer')) pos
                  FROM applications a WHERE a.status IN ({ph}) GROUP BY v HAVING n >= 3 ORDER BY pos*1.0/n DESC LIMIT 5""",
              SUBMITTED_LIKE)
    if rv:
        lines.append("\nRESUME VERSIONS (3+ uses)")
        lines += [f"  {r['v']:28}{r['n']:>5} sent, {r['pos'] or 0} interviews" for r in rv]

    today = datetime.now().date().isoformat()
    fu = db.q("""SELECT a.id, j.title, j.company, a.follow_up_on FROM applications a JOIN jobs j ON j.id=a.job_id
                 WHERE a.follow_up_on IS NOT NULL AND a.follow_up_on <= ? AND a.status IN ('submitted','submitted_unverified')
                 ORDER BY a.follow_up_on""", (today,))
    lines.append("\nFOLLOW-UPS DUE")
    lines += [f"  [{r['id']}] {r['title']} @ {r['company']} (due {r['follow_up_on']})" for r in fu] or ["  none"]

    waiting = db.q("""SELECT a.id, j.title, j.company, a.status, substr(a.notes,1,90) n FROM applications a
                      JOIN jobs j ON j.id=a.job_id WHERE a.status IN ('awaiting_approval','needs_human')
                      ORDER BY a.id LIMIT 25""")
    lines.append("\nWAITING ON YOU")
    lines += [f"  [{r['id']}] {r['status']:18} {r['title']} @ {r['company']}  - {r['n'] or ''}" for r in waiting] or ["  nothing"]

    unver = db.one("SELECT COUNT(*) c FROM applications WHERE status='submitted_unverified'")["c"]
    if unver:
        lines.append(f"\n{unver} submission(s) had no confirmation page - check your email and mark them with "
                     f"`status <id> submitted` once confirmed.")
    return "\n".join(lines)


def list_jobs(db: DB, status: str = "scored", limit: int = 30) -> str:
    rows = db.q("""SELECT id, score, role_family, title, company, location, platform, filter_reason, deadline, url
                   FROM jobs WHERE status=? ORDER BY score DESC, first_seen_at DESC LIMIT ?""", (status, limit))
    out = []
    for r in rows:
        extra = f"  [{r['filter_reason']}]" if r["filter_reason"] else ""
        dl = f"  deadline {r['deadline']}" if r["deadline"] else ""
        out.append(f"#{r['id']:<5} {r['score'] or 0:>5.1f}  {str(r['role_family']):22} {r['title'][:45]:45} "
                   f"{r['company'][:22]:22} {(r['location'] or '')[:18]:18} {r['platform']}{dl}{extra}\n       {r['url']}")
    return "\n".join(out) or "(no jobs)"


def audit_view(db: DB, app_id: int) -> str:
    app = db.one("SELECT * FROM applications WHERE id=?", (app_id,))
    if not app:
        return f"no application {app_id}"
    job = db.one("SELECT * FROM jobs WHERE id=?", (app["job_id"],))
    lines = [f"Application {app_id}: {job['title']} @ {job['company']}",
             f"  posting:        {job['url']}",
             f"  why selected:   {app['selection_reason']}",
             f"  resume:         {app['resume_version']}  ({app['resume_path']})",
             f"  cover letter:   {app['cover_path']}",
             f"  approval:       {app['approval']}  at {app['approved_at'] or '-'}",
             f"  status:         {app['status']}",
             f"  verification:   {app['verification'] or '-'}",
             f"  follow up on:   {app['follow_up_on'] or '-'}", "  form answers:"]
    for label, a in json.loads(app["answers"] or "{}").items():
        lines.append(f"    {label[:60]:60} = {str(a.get('value'))[:40]}  [{a.get('confidence')}]")
    lines.append("  events:")
    for e in db.q("SELECT at, event, detail FROM audit WHERE app_id=? OR (job_id=? AND app_id IS NULL) ORDER BY id",
                  (app_id, app["job_id"])):
        lines.append(f"    {e['at']}  {e['event']}  {(e['detail'] or '')[:160]}")
    return "\n".join(lines)


def export_csv(db: DB, path: Path) -> Path:
    rows = db.q("""SELECT a.id app_id, j.title, j.company, j.location, j.role_family, j.score, j.source, j.url,
                   a.status, a.approval, a.resume_version, a.created_at, a.submitted_at, a.follow_up_on, a.verification
                   FROM applications a JOIN jobs j ON j.id=a.job_id ORDER BY a.id""")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if rows:
            w.writerow(rows[0].keys())
            for r in rows:
                w.writerow(list(r))
    return path
