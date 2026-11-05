"""Mirror local read-models to Supabase for the public portfolio showcase.

SQLite stays the source of truth. This pushes a PRIVACY-FILTERED subset — job
postings, application status (no raw form answers, no profile, no audit detail),
and a dashboard snapshot — to Supabase so the Next.js frontend can read them
under row-level security with the public anon key.

Credentials (local only, never committed) in private/.env:
    SUPABASE_URL=https://<ref>.supabase.co
    SUPABASE_SERVICE_ROLE_KEY=<service_role key>   # bypasses RLS; server-side only

Writes go through the PostgREST API with the service key. (Alternative: a direct
Postgres connection string + psycopg — cleaner for very large syncs, but needs the
DB password. REST is used here so the agent only needs the service key.)
"""
from __future__ import annotations

import os

import requests

from . import api
from .db import DB

JOB_STATUSES = ("scored", "prepared", "applied", "filtered")
JOB_COLS = ("id", "score", "role_family", "title", "company", "location", "platform",
            "remote", "filter_reason", "deadline", "salary_min", "salary_max",
            "url", "status", "missing", "first_seen_at")
APP_COLS = ("id", "job_id", "status", "resume_version", "selection_reason", "approval",
            "submitted_at", "follow_up_on", "verification", "title", "company",
            "platform", "score", "url")


def _creds() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not (url and key):
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set in private/.env")
    return url.rstrip("/"), key


def _headers(key: str, extra: dict | None = None) -> dict:
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def _replace(base: str, key: str, table: str, rows: list[dict]) -> int:
    """Clear a table and insert the given rows (full replace)."""
    rest = f"{base}/rest/v1/{table}"
    # Delete everything (id >= 0 matches all rows).
    d = requests.delete(rest, params={"id": "gte.0"},
                        headers=_headers(key, {"Prefer": "return=minimal"}), timeout=30)
    d.raise_for_status()
    if rows:
        r = requests.post(rest, json=rows,
                        headers=_headers(key, {"Prefer": "return=minimal"}), timeout=60)
        if not r.ok:
            raise SystemExit(f"insert into {table} failed: {r.status_code} {r.text[:300]}")
    return len(rows)


def _pick(row: dict, cols) -> dict:
    out = {c: row.get(c) for c in cols}
    if "remote" in out:
        out["remote"] = bool(out.get("remote"))
    return out


def run(db: DB) -> dict:
    base, key = _creds()

    jobs: list[dict] = []
    seen: set[int] = set()
    for status in JOB_STATUSES:
        for j in api.jobs(db, status, limit=1000):
            if j["id"] not in seen:
                seen.add(j["id"])
                jobs.append(_pick(j, JOB_COLS))

    apps = [_pick(a, APP_COLS) for a in api.applications(db, None, limit=1000)]

    stats = api.dashboard(db)

    n_jobs = _replace(base, key, "jobs", jobs)
    n_apps = _replace(base, key, "applications", apps)

    # Single-row dashboard snapshot (upsert on id=1).
    rest = f"{base}/rest/v1/stats"
    r = requests.post(rest, json=[{"id": 1, "data": stats}],
                      headers=_headers(key, {"Prefer": "resolution=merge-duplicates,return=minimal"}),
                      timeout=30)
    if not r.ok:
        raise SystemExit(f"stats upsert failed: {r.status_code} {r.text[:300]}")

    return {"jobs": n_jobs, "applications": n_apps, "stats": 1, "project": base}
