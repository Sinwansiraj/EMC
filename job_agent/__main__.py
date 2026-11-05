"""Command line: python -m job_agent <command>"""
from __future__ import annotations

import argparse
import logging
import sys

from .config import PRIVATE, ROOT, load_companies, load_config, load_env, load_profile
from .db import DB


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="job_agent", description="Personal job search and application agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="discover -> score -> prepare -> apply (the daily routine)")
    r.add_argument("--max", type=int, default=None, help="max applications to attempt this run")
    r.add_argument("--headless", action="store_true")
    r.add_argument("--no-interactive", action="store_true", help="never prompt; unapproved items wait for review")

    sub.add_parser("discover", help="fetch new jobs from all sources")
    s = sub.add_parser("score", help="score and rank discovered jobs")
    s.add_argument("--rescore", action="store_true", help="re-score everything not yet applied (after editing profile)")
    j = sub.add_parser("jobs", help="list jobs")
    j.add_argument("--status", default="scored", help="scored | filtered | prepared | applied | duplicate | discovered")
    j.add_argument("--limit", type=int, default=30)
    p = sub.add_parser("prepare", help="build resume/cover letter packs for the top jobs")
    p.add_argument("--limit", type=int, default=None)
    a = sub.add_parser("apply", help="fill and submit prepared applications")
    a.add_argument("--max", type=int, default=None)
    a.add_argument("--headless", action="store_true")
    a.add_argument("--no-interactive", action="store_true")
    a.add_argument("--ids", type=int, nargs="*", help="only these application ids")
    rv = sub.add_parser("review", help="approve or reject applications waiting for you")
    rv.add_argument("--approve", type=int, nargs="*", default=[])
    rv.add_argument("--reject", type=int, nargs="*", default=[])
    st = sub.add_parser("status", help="record an outcome, e.g. status 12 interview 'HR call Monday'")
    st.add_argument("app_id", type=int)
    st.add_argument("outcome")
    st.add_argument("note", nargs="?", default="")
    sub.add_parser("report", help="progress summary, follow-ups and what's working")
    au = sub.add_parser("audit", help="full audit trail for one application")
    au.add_argument("app_id", type=int)
    ex = sub.add_parser("export", help="export applications to CSV")
    ex.add_argument("--out", default=str(PRIVATE / "applications.csv"))
    q = sub.add_parser("ask", help="test how a form question would be answered")
    q.add_argument("question", nargs="+")
    sub.add_parser("check-boards", help="verify the company board tokens in config/companies.yaml")
    sub.add_parser("sync-supabase", help="mirror read-models to Supabase for the public showcase")
    sub.add_parser("seekers", help="list consented Supabase seekers and whether each role has a resume")
    sub.add_parser("seed-demo", help="insert demo jobs/applications into the local DB (for the showcase)")
    sub.add_parser("keygen", help="generate an encryption key for the profile")
    sub.add_parser("encrypt-profile", help="encrypt private/profile.yaml with JOB_AGENT_KEY")

    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env()

    if args.cmd == "keygen":
        from .privacy import keygen
        print(keygen())
        print("Store this as JOB_AGENT_KEY in your environment (not in the project folder).")
        return
    if args.cmd == "encrypt-profile":
        from .privacy import encrypt_file
        print("Encrypted ->", encrypt_file(PRIVATE / "profile.yaml"))
        return

    cfg = load_config()
    if args.cmd == "check-boards":
        from .sources import ats
        from .sources.base import Http
        http = Http(min_interval=1.0)
        for name, fn in ats.FETCHERS.items():
            for token in load_companies(cfg).get(name) or []:
                try:
                    n = len(fn(http, token, []))
                    print(f"  ok   {name}/{token}: {n} open jobs")
                except Exception as e:  # noqa: BLE001
                    print(f"  FAIL {name}/{token}: {e}")
        return

    profile = load_profile()
    db = DB(PRIVATE / "tracker.db")

    if args.cmd == "ask":
        from .answers import Answerer
        a_ = Answerer(profile).answer(" ".join(args.question))
        print(f"{a_.value!r}  [{a_.confidence}] {a_.note}")
        return

    if args.cmd == "seed-demo":
        from . import demo
        print("seeded:", demo.run(db))
        return

    if args.cmd == "sync-supabase":
        from . import mirror
        print("mirror:", mirror.run(db))
        return

    if args.cmd == "seekers":
        from . import seekers
        print(seekers.report_text())
        return

    from . import apply as apply_mod
    from . import discover, matcher, prepare, tracker

    if args.cmd in ("run", "discover"):
        st_ = discover.run(db, cfg)
        print(f"discover: {st_['new']} new, {st_['duplicates_merged']} duplicates merged, {st_['seen']} seen")
        for e in st_["errors"]:
            print("  source error:", e)
        if args.cmd == "discover":
            return
    if args.cmd in ("run", "score"):
        print("score:", matcher.run(db, profile, cfg, rescore=getattr(args, "rescore", False)))
        if args.cmd == "score":
            return
    if args.cmd == "jobs":
        print(tracker.list_jobs(db, args.status, args.limit))
        return
    if args.cmd in ("run", "prepare"):
        print("prepare:", prepare.run(db, profile, cfg, getattr(args, "limit", None) or getattr(args, "max", None)))
        if args.cmd == "prepare":
            return
    if args.cmd in ("run", "apply"):
        interactive = False if args.no_interactive else None
        print("apply:", apply_mod.run(db, profile, cfg, interactive=interactive, headless=args.headless,
                                      max_apps=args.max, only_ids=getattr(args, "ids", None)))
        tracker.sweep_no_response(db, cfg)
        return
    if args.cmd == "review":
        for i in args.approve:
            db.update_app(i, status="approved", approval="approved_by_user_pending_fill")
            db.audit("approved_in_review", None, app_id=i)
        for i in args.reject:
            db.update_app(i, status="withdrawn", approval="declined_by_user")
            db.audit("declined_by_user", None, app_id=i)
        rows = db.q("""SELECT a.id, j.score, j.title, j.company, j.platform, a.status, a.selection_reason, a.notes
                       FROM applications a JOIN jobs j ON j.id=a.job_id
                       WHERE a.status IN ('prepared','awaiting_approval','needs_human') ORDER BY j.score DESC""")
        for r_ in rows:
            print(f"[{r_['id']}] {r_['score']:.0f}  {r_['title']} @ {r_['company']} ({r_['platform']}) - {r_['status']}")
            print(f"      why: {r_['selection_reason']}")
            if r_["notes"]:
                print(f"      needs: {r_['notes']}")
        if not rows:
            print("Nothing waiting for review.")
        else:
            print("\nApprove: python -m job_agent review --approve 3 5 8   then   python -m job_agent apply --ids 3 5 8")
        return
    if args.cmd == "status":
        tracker.set_status(db, args.app_id, args.outcome, args.note)
        print("updated")
        return
    if args.cmd == "report":
        tracker.sweep_no_response(db, cfg)
        print(tracker.summary(db))
        return
    if args.cmd == "audit":
        print(tracker.audit_view(db, args.app_id))
        return
    if args.cmd == "export":
        from pathlib import Path
        print("written:", tracker.export_csv(db, Path(args.out)))
        return


if __name__ == "__main__":
    sys.exit(main())
