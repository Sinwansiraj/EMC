"""SQLite tracker: jobs, applications, and an append-only audit trail."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .privacy import ensure_private_dir, restrict

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id            INTEGER PRIMARY KEY,
    fingerprint   TEXT UNIQUE NOT NULL,      -- company+title+location, normalised
    source        TEXT NOT NULL,             -- greenhouse, lever, linkedin_alert, ...
    platform      TEXT NOT NULL,             -- where the application happens
    external_id   TEXT,
    url           TEXT NOT NULL,             -- original posting URL
    apply_url     TEXT,
    title         TEXT NOT NULL,
    company       TEXT NOT NULL,
    location      TEXT,
    remote        INTEGER DEFAULT 0,
    description   TEXT,
    salary_min    INTEGER,
    salary_max    INTEGER,
    posted_at     TEXT,
    deadline      TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL,
    also_seen_at  TEXT DEFAULT '[]',          -- other URLs/sources for the same job
    role_family   TEXT,
    score         REAL,
    score_detail  TEXT,                       -- JSON breakdown
    missing       TEXT,                       -- JSON list of missing requirements
    filter_reason TEXT,                       -- why it was excluded, if it was
    status        TEXT DEFAULT 'discovered'
);
CREATE TABLE IF NOT EXISTS applications (
    id              INTEGER PRIMARY KEY,
    job_id          INTEGER NOT NULL REFERENCES jobs(id),
    status          TEXT NOT NULL,   -- prepared, awaiting_approval, approved, submitted,
                                     -- submitted_unverified, needs_human, failed, interview,
                                     -- offer, rejected, withdrawn, no_response
    resume_path     TEXT,
    resume_version  TEXT,
    cover_path      TEXT,
    answers         TEXT,            -- JSON {question: {answer, source, confidence}}
    selection_reason TEXT,
    approval        TEXT,            -- none | pending | approved_by_user | auto_policy
    approved_at     TEXT,
    submitted_at    TEXT,
    verification    TEXT,            -- evidence that the submission landed
    follow_up_on    TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id        INTEGER PRIMARY KEY,
    at        TEXT NOT NULL,
    job_id    INTEGER,
    app_id    INTEGER,
    event     TEXT NOT NULL,
    detail    TEXT
);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS ix_apps_job ON applications(job_id);
CREATE INDEX IF NOT EXISTS ix_apps_status ON applications(status);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DB:
    def __init__(self, path: Path):
        ensure_private_dir(path.parent)
        self.path = path
        self.con = sqlite3.connect(path)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        self.con.commit()
        restrict(path)

    # ---------- generic ----------
    def q(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        return self.con.execute(sql, args).fetchall()

    def one(self, sql: str, args: tuple = ()):
        return self.con.execute(sql, args).fetchone()

    def x(self, sql: str, args: tuple = ()) -> int:
        cur = self.con.execute(sql, args)
        self.con.commit()
        return cur.lastrowid

    def audit(self, event: str, detail=None, job_id=None, app_id=None) -> None:
        if detail is not None and not isinstance(detail, str):
            detail = json.dumps(detail, ensure_ascii=False, default=str)
        self.x("INSERT INTO audit(at, job_id, app_id, event, detail) VALUES (?,?,?,?,?)",
               (now(), job_id, app_id, event, detail))

    def get_meta(self, k: str, default=None):
        r = self.one("SELECT v FROM meta WHERE k=?", (k,))
        return r["v"] if r else default

    def set_meta(self, k: str, v: str) -> None:
        self.x("INSERT INTO meta(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))

    # ---------- applications ----------
    def update_app(self, app_id: int, **fields) -> None:
        fields["updated_at"] = now()
        cols = ", ".join(f"{k}=?" for k in fields)
        self.x(f"UPDATE applications SET {cols} WHERE id=?", (*fields.values(), app_id))

    def submitted_today(self) -> int:
        # "Today" is the local calendar day (your machine's timezone), compared in UTC.
        local_midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        since = local_midnight.astimezone(timezone.utc).isoformat(timespec="seconds")
        r = self.one("SELECT COUNT(*) c FROM applications WHERE submitted_at >= ?", (since,))
        return r["c"]
