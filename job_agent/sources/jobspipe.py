"""JobsPipe jobs API (api.jobspipe.dev): LinkedIn, Indeed, ATS career sites and remote boards in one
schema. Needs JOBSPIPE_API_KEY in private/.env.

Billing: 1 credit per job returned, charged once per job per calendar month (a repeat within the month
is free). The free plan is a one-time grant of 1,000 credits, so this source is deliberately frugal:
  - narrow searches (India + your cities, India + remote; target titles only; senior titles excluded)
  - delta polling: after one search has been read to the end, later runs return only new postings
  - a hard credit budget per run, and a stop when the account's remaining credits run low
LinkedIn/Indeed postings found here are still "assist" (you apply); ATS links keep their usual policy.
"""
from __future__ import annotations

import json
import os
import time

from .base import Job, html_to_text, parse_deadline
from .feeds import detect_platform

SEARCH_URL = "https://api.jobspipe.dev/v1/jobs/search"


def to_job(j: dict) -> Job | None:
    title, company = (j.get("job_title") or "").strip(), (j.get("company") or "").strip()
    url = j.get("url") or j.get("source_url") or ""
    if not (title and company and url):
        return None
    desc = html_to_text(j.get("description"))
    smin = smax = None
    if (j.get("salary_currency") or "").upper() == "INR":
        smin = int(j["min_annual_salary"]) if j.get("min_annual_salary") else None
        smax = int(j["max_annual_salary"]) if j.get("max_annual_salary") else None
    remote = bool(j.get("remote")) or j.get("work_arrangement") == "remote"
    loc = j.get("location") or j.get("country") or ""
    if remote and "remote" not in loc.lower():
        loc = f"Remote ({loc})" if loc else "Remote"
    providers = [s.get("provider") for s in (j.get("sources") or []) if isinstance(s, dict)]
    return Job(
        source="jobspipe", platform=detect_platform(url), external_id=str(j.get("id") or url),
        url=url, apply_url=url, title=title, company=company, location=loc, description=desc,
        remote=remote, salary_min=smin, salary_max=smax,
        posted_at=(j.get("date_posted") or "")[:10] or None,
        deadline=(j.get("expires_at") or "")[:10] or parse_deadline(desc),
        extra={"via": providers, "seniority": j.get("seniority"), "ghost_score": j.get("ghost_score"),
               "salary_string": j.get("salary_string"), "visa": j.get("visa_sponsorship")},
    )


def build_searches(cfg: dict, titles: list[str]) -> dict[str, dict]:
    base = {
        "job_title_or": titles[:60],
        "job_title_not": cfg.get("exclude_title_words", [])[:100],
        "job_country_code_or": [cfg.get("country_code", "IN")],
        "posted_at_max_age_days": int(cfg.get("max_age_days", 3)),
    }
    if cfg.get("max_ghost_score") is not None:
        base["max_ghost_score"] = cfg["max_ghost_score"]
    out = {}
    if cfg.get("cities"):
        out["cities"] = {**base, "city_or": cfg["cities"]}
    if cfg.get("remote", True):
        out["remote"] = {**base, "remote": True}
    return out


def target_titles(app_cfg: dict, extra: list[str]) -> list[str]:
    seen, out = set(), []
    for p in app_cfg.get("profiles", {}).values():
        for t in p.get("titles", []):
            if t.lower() not in seen:
                seen.add(t.lower()); out.append(t)
    for t in extra:
        if t.lower() not in seen:
            seen.add(t.lower()); out.append(t)
    return out


def fetch(http, db, app_cfg: dict, cfg: dict) -> tuple[list[Job], list[str], dict]:
    key = os.environ.get("JOBSPIPE_API_KEY")
    if not key:
        return [], ["jobspipe: JOBSPIPE_API_KEY not set in private/.env"], {}
    s = http.s
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    budget = int(cfg.get("max_credits_per_run", 60))
    reserve = int(cfg.get("stop_when_credits_below", 50))
    page_size = int(cfg.get("page_size", 25))
    titles = target_titles(app_cfg, cfg.get("extra_titles", []))
    jobs: dict[str, Job] = {}
    errors: list[str] = []
    stats = {"credits_charged": 0, "credits_remaining": None, "pages": 0}

    for name, filters in build_searches(cfg, titles).items():
        meta_key = f"jobspipe_delta:{name}"
        sig = json.dumps(filters, sort_keys=True)
        saved = json.loads(db.get_meta(meta_key) or "{}")
        delta = saved.get("cursor") if saved.get("sig") == sig else None   # filters changed -> start over
        cursor = None
        while True:
            if stats["credits_charged"] + page_size > budget:
                errors.append(f"jobspipe {name}: stopped at per-run budget of {budget} credits; continues next run")
                break
            if stats["credits_remaining"] is not None and stats["credits_remaining"] - page_size < reserve:
                errors.append(f"jobspipe: {stats['credits_remaining']} credits left - stopped to keep a {reserve}-credit reserve")
                return list(jobs.values()), errors, stats
            body = {**filters, "limit": page_size}
            if cursor:
                body["cursor"] = cursor
            elif delta:
                body["delta_cursor"] = delta
            if stats["pages"]:
                time.sleep(0.6)          # stay well under the plan's per-second limit
            r = s.post(SEARCH_URL, headers=headers, json=body, timeout=http.timeout)
            stats["pages"] += 1
            if r.status_code == 429:
                errors.append("jobspipe: rate limited (429); continues next run")
                break
            if r.status_code in (401, 403):
                return list(jobs.values()), errors + [f"jobspipe: HTTP {r.status_code} - check the API key"], stats
            if r.status_code == 402:
                return list(jobs.values()), errors + ["jobspipe: out of credits (402)"], stats
            if not r.ok:
                errors.append(f"jobspipe {name}: HTTP {r.status_code} {r.text[:200]}")
                break
            data = r.json()
            meta = data.get("metadata", {}) or {}
            stats["credits_charged"] += int(meta.get("credits_charged") or 0)
            if meta.get("credits_remaining") is not None:
                stats["credits_remaining"] = int(meta["credits_remaining"])
            for raw in data.get("data", []) or []:
                j = to_job(raw)
                if j:
                    jobs.setdefault(j.external_id, j)
            cursor = meta.get("next_cursor")
            if not cursor:
                nxt = meta.get("next_delta_cursor")
                if nxt:   # read to the end: from now on only new postings come back
                    db.set_meta(meta_key, json.dumps({"sig": sig, "cursor": nxt}))
                break
    return list(jobs.values()), errors, stats
