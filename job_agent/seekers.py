"""Read consented job seekers from Supabase and decide who the agent may apply for.

The rule: a seeker is READY only when every role they target has a matching resume
uploaded. If they target Data Analyst, Data Scientist and Customer Support, all three
resumes must be present; otherwise the agent holds off on the uncovered roles.

Role codes are the agent's own families (job_agent/tailor.py FAMILY_FOCUS), so a
matched resume plugs straight into documents.master_resumes[<family>] when applying.

Reads with the service key (bypasses RLS). Needs SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY
in private/.env — the same credentials the mirror uses.
"""
from __future__ import annotations

import requests

from .mirror import _creds, _headers


def readiness(target_roles: list[str], resume_roles: list[str]) -> dict:
    """Match targeted roles against roles that have a resume. Pure / testable."""
    seen: set[str] = set()
    targets: list[str] = []
    for r in target_roles:
        r = (r or "").strip()
        if r and r not in seen:
            seen.add(r)
            targets.append(r)
    have = set(resume_roles)
    covered = [r for r in targets if r in have]
    missing = [r for r in targets if r not in have]
    extra = [r for r in sorted(have) if r not in seen]  # resumes for non-targeted roles
    return {
        "targets": targets,
        "covered": covered,
        "missing": missing,
        "extra": extra,
        "ready": bool(targets) and not missing,
    }


def _split_roles(value: str | None) -> list[str]:
    return [p.strip() for p in (value or "").replace(";", ",").split(",") if p.strip()]


def fetch_seekers() -> list[dict]:
    """Consented seekers with their resumes and a readiness verdict."""
    base, key = _creds()
    s = requests.get(f"{base}/rest/v1/job_seekers",
                     params={"select": "*", "consent": "eq.true", "order": "created_at.desc"},
                     headers=_headers(key), timeout=30)
    s.raise_for_status()
    r = requests.get(f"{base}/rest/v1/resumes", params={"select": "*"},
                     headers=_headers(key), timeout=30)
    r.raise_for_status()

    by_seeker: dict[str, list[dict]] = {}
    for row in r.json():
        by_seeker.setdefault(row["seeker_id"], []).append(row)

    out = []
    for seeker in s.json():
        resumes = by_seeker.get(seeker["id"], [])
        resume_roles = [x["target_role"] for x in resumes]
        verdict = readiness(_split_roles(seeker.get("target_roles")), resume_roles)
        out.append({"seeker": seeker, "resumes": resumes, **verdict})
    return out


def report_text() -> str:
    rows = fetch_seekers()
    if not rows:
        return "No consented seekers yet."
    lines = []
    ready = 0
    for row in rows:
        s = row["seeker"]
        tag = "READY" if row["ready"] else "BLOCKED"
        ready += row["ready"]
        lines.append(f"[{tag}] {s.get('full_name')} <{s.get('email')}>")
        lines.append(f"    targets:  {', '.join(row['targets']) or '(none)'}")
        lines.append(f"    resumes:  {', '.join(row['covered']) or '(none)'}")
        if row["missing"]:
            lines.append(f"    MISSING:  {', '.join(row['missing'])}  -> agent will not apply to these")
        if row["extra"]:
            lines.append(f"    (extra resumes for non-targeted roles: {', '.join(row['extra'])})")
    lines.append(f"\n{ready}/{len(rows)} seeker(s) ready to apply.")
    return "\n".join(lines)
