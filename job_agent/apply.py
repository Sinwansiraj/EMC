"""Run applications: fill forms, apply the approval gate, submit, verify, and log everything."""
from __future__ import annotations

import json
import random
import sys
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from . import formfill
from .answers import Answerer
from .config import PRIVATE
from .db import DB, now
from .discover import norm_company
from .privacy import ensure_private_dir, redact, restrict


# ------------------------------------------------------------------ policy
def platform_policy(job: dict, cfg: dict) -> str:
    host = urlparse(job.get("apply_url") or job["url"]).hostname or ""
    if any(host == d or host.endswith("." + d) for d in cfg.get("trusted_career_domains") or []):
        return "auto"
    return cfg["platforms"].get(job["platform"], cfg["platforms"].get("other", "assist"))


def approval_phase_active(db: DB, cfg: dict) -> tuple[bool, str]:
    a = cfg["autonomy"]
    first = db.get_meta("first_apply_at")
    if not first:
        db.set_meta("first_apply_at", now())
        first = db.get_meta("first_apply_at")
    days = (datetime.now(timezone.utc) - datetime.fromisoformat(first)).days
    reviewed = db.one("SELECT COUNT(*) c FROM applications WHERE approval='approved_by_user'")["c"]
    if days < a["approval_phase_days"] or reviewed < a["approval_phase_min_reviewed"]:
        return True, (f"approval phase: day {days + 1}/{a['approval_phase_days']}, "
                      f"{reviewed}/{a['approval_phase_min_reviewed']} applications reviewed by you")
    return False, "approval phase complete"


def auto_gates(job: dict, app: dict, fill, policy: str, cfg: dict, phase_active: bool) -> list[str]:
    req = cfg["autonomy"]["auto_submit_requires"]
    failed = []
    if phase_active:
        failed.append("approval phase still active")
    if policy != req["platform_policy"]:
        failed.append(f"platform policy is '{policy}'")
    if job["score"] < req["min_score"]:
        failed.append(f"score {job['score']:.0f} < {req['min_score']}")
    if req["no_unanswered_required_fields"] and fill.unresolved:
        failed.append("unanswered required: " + "; ".join(fill.unresolved[:5]))
    if req["no_review_flagged_answers"] and fill.review:
        failed.append("answers flagged for review: " + "; ".join(fill.review[:3]))
    if req["no_captcha"] and fill.captcha:
        failed.append("CAPTCHA present - the agent never solves these")
    if fill.errors:
        failed.append("form errors: " + "; ".join(fill.errors[:3]))
    if not fill.submit_ready:
        failed.append("could not reach the submit step")
    if req["invention_guard_passed"] and (app.get("notes") or "").startswith("invention guard"):
        failed.append(app["notes"])
    return failed


# ------------------------------------------------------------------ assist mode (LinkedIn, Naukri, ...)
COMMON_QUESTIONS = [
    "Full name", "Email", "Phone", "Current location", "LinkedIn profile", "Total experience (years)",
    "Relevant experience (years)", "Current CTC", "Expected CTC", "Expected monthly salary", "Notice period",
    "When can you join?", "Willing to relocate?", "Highest qualification", "Years of experience with Python",
    "Years of experience with SQL", "Have you used Power BI?", "Authorized to work in India?",
    "Will you require visa sponsorship?", "Reason for leaving",
]


def answer_sheet(profile: dict) -> str:
    a = Answerer(profile)
    lines = []
    for q in COMMON_QUESTIONS:
        ans = a.answer(q)
        note = f"   ({ans.note})" if ans.note else ""
        lines.append(f"{q}: {ans.value}{note}")
    return "\n".join(lines)


def assist(db: DB, job: dict, app: dict, profile: dict, interactive: bool) -> None:
    folder = Path(app["cover_path"]).parent
    sheet = folder / "answer_sheet.txt"
    sheet.write_text(answer_sheet(profile), encoding="utf-8")
    restrict(sheet)
    db.update_app(app["id"], status="needs_human", approval="pending",
                  notes=f"{job['platform']} does not allow automated applying - apply yourself with this pack")
    db.audit("assist_pack_ready", {"platform": job["platform"], "url": job["url"], "pack": str(folder)},
             job_id=job["id"], app_id=app["id"])
    if interactive:
        print(f"\n[{app['id']}] {job['title']} @ {job['company']}  ({job['platform']}, manual)")
        print(f"     resume: {app['resume_path']}\n     cover letter: {app['cover_path']}\n     answers: {sheet}")
        if input("     Open the job page now? [y/N] ").strip().lower() == "y":
            webbrowser.open(job["url"])
            done = input("     Did you submit it? [y/N] ").strip().lower()
            if done == "y":
                mark_submitted(db, app["id"], job["id"], "approved_by_user", "user confirmed manual submission",
                               "submitted")


# ------------------------------------------------------------------ bookkeeping
def mark_submitted(db: DB, app_id: int, job_id: int, approval: str, evidence: str, status: str, cfg=None) -> None:
    days = (cfg or {}).get("tracking", {}).get("follow_up_after_days", 7)
    follow = (datetime.now().date() + timedelta(days=days)).isoformat()
    ts = now()
    db.update_app(app_id, status=status, approval=approval, approved_at=ts, submitted_at=ts,
                  verification=evidence, follow_up_on=follow)
    db.x("UPDATE jobs SET status='applied' WHERE id=?", (job_id,))
    db.audit("submitted", {"status": status, "approval": approval, "evidence": evidence}, job_id=job_id, app_id=app_id)


def previously_applied(db: DB, job: dict) -> bool:
    comp = norm_company(job["company"])
    r = db.one("""SELECT COUNT(*) c FROM applications a JOIN jobs j ON j.id=a.job_id
                  WHERE a.submitted_at IS NOT NULL AND j.fingerprint LIKE ?""", (comp + "|%",))
    return r["c"] > 0


# ------------------------------------------------------------------ main loop
def run(db: DB, profile: dict, cfg: dict, interactive: bool | None = None, headless: bool = False,
        max_apps: int | None = None, only_ids: list[int] | None = None) -> dict:
    interactive = sys.stdin.isatty() if interactive is None else interactive
    stats = {"submitted": 0, "submitted_unverified": 0, "awaiting_approval": 0, "assist": 0,
             "failed": 0, "skipped": 0}
    where = "a.status IN ('prepared','approved')"
    args: tuple = ()
    if only_ids:
        where = f"a.id IN ({','.join('?' * len(only_ids))})"
        args = tuple(only_ids)
    rows = db.q(f"""SELECT a.*, j.title, j.company, j.url, j.apply_url, j.platform, j.score, j.role_family,
                    j.fingerprint, j.id AS jid FROM applications a JOIN jobs j ON j.id=a.job_id
                    WHERE {where} ORDER BY j.score DESC""", args)
    if not rows:
        return stats
    phase_active, phase_note = approval_phase_active(db, cfg)
    print(phase_note)

    answerer = Answerer(profile)
    browser_ctx = None
    pw = None
    cap = cfg["limits"]["daily_application_cap"]
    try:
        for i, r in enumerate(rows):
            if max_apps is not None and i >= max_apps:
                break
            if db.submitted_today() >= cap:
                print(f"Daily cap of {cap} reached; stopping.")
                break
            app, job = dict(r), {**dict(r), "id": r["jid"]}
            policy = platform_policy(job, cfg)
            if policy == "assist":
                assist(db, job, app, profile, interactive)
                stats["assist"] += 1
                continue

            if browser_ctx is None:
                from playwright.sync_api import sync_playwright
                pw = sync_playwright().start()
                prof_dir = ensure_private_dir(PRIVATE / "browser")
                browser_ctx = pw.chromium.launch_persistent_context(str(prof_dir), headless=headless,
                                                                     viewport={"width": 1280, "height": 900})
            page = browser_ctx.new_page()
            folder = Path(app["cover_path"]).parent
            docs = {"resume_path": app["resume_path"], "cover_path": app["cover_path"],
                    "cover_text": (folder / "cover_letter.txt").read_text(encoding="utf-8"),
                    "resume_version": app["resume_version"]}
            try:
                formfill.open_application(page, job["apply_url"] or job["url"])
                res = formfill.fill(page, answerer, docs, previously_applied(db, job))
            except Exception as e:  # noqa: BLE001
                db.update_app(app["id"], status="failed", notes=redact(f"fill error: {e}", profile))
                db.audit("fill_failed", redact(str(e), profile), job_id=job["id"], app_id=app["id"])
                stats["failed"] += 1
                page.close()
                continue

            shot = folder / "before_submit.png"
            page.screenshot(path=str(shot), full_page=True)
            restrict(shot)
            db.update_app(app["id"], answers=json.dumps(res.answers, ensure_ascii=False))
            gates = auto_gates(job, app, res, policy, cfg, phase_active)
            db.audit("form_filled", {"steps": res.steps, "unresolved": res.unresolved, "review": res.review,
                                     "captcha": res.captcha, "gates_failed": gates}, job_id=job["id"], app_id=app["id"])

            approval = None
            if not gates:
                approval = "auto_policy"
            elif app["status"] == "approved" and not res.captcha and not res.unresolved and not res.review:
                approval = "approved_by_user"     # approved earlier via `review`
            elif interactive:
                print(f"\n[{app['id']}] {job['title']} @ {job['company']}  score {job['score']:.0f}")
                print("     why: " + app["selection_reason"])
                for label, a in res.answers.items():
                    flag = "" if a["confidence"] in ("exact", "prefilled") else f"  <- {a['confidence']}: {a['note']}"
                    print(f"     {label[:60]:60} = {str(a['value'])[:50]}{flag}")
                for g in gates:
                    print(f"     needs you: {g}")
                print("     The form is open in the browser. Fix anything there (including a CAPTCHA) before answering.")
                choice = input("     Submit now? [y]es / [n]o, skip / [l]ater: ").strip().lower()
                if choice == "y":
                    approval = "approved_by_user"
                elif choice == "n":
                    db.update_app(app["id"], status="withdrawn", approval="declined_by_user")
                    db.x("UPDATE jobs SET status='skipped' WHERE id=?", (job["id"],))
                    db.audit("declined_by_user", None, job_id=job["id"], app_id=app["id"])
                    stats["skipped"] += 1
                    page.close()
                    continue

            if not approval:
                db.update_app(app["id"], status="awaiting_approval", approval="pending",
                              notes="; ".join(gates))
                stats["awaiting_approval"] += 1
                page.close()
                continue

            status, evidence = formfill.submit_and_verify(page)
            after = folder / "after_submit.png"
            page.screenshot(path=str(after), full_page=True)
            restrict(after)
            if status == "failed":
                db.update_app(app["id"], status="failed", approval=approval, notes=evidence)
                db.audit("submit_failed", evidence, job_id=job["id"], app_id=app["id"])
                stats["failed"] += 1
            else:
                mark_submitted(db, app["id"], job["id"], approval, evidence, status, cfg)
                stats[status] += 1
            page.close()
            lo, hi = cfg["limits"]["seconds_between_submissions"]
            time.sleep(random.uniform(lo, hi))
    finally:
        if browser_ctx:
            browser_ctx.close()
        if pw:
            pw.stop()
    return stats
