"""Official public job-board APIs: Greenhouse, Lever, Ashby, Workable.

These endpoints are published by the ATS vendors for exactly this purpose (listing a company's
open jobs), so polling them is permitted. Each company is fetched at most once per run.
"""
from __future__ import annotations

import logging

from .base import Http, Job, html_to_text, is_remote, iso, parse_deadline, parse_salary_inr

log = logging.getLogger(__name__)


def _finish(job: Job, remote_kw: list[str]) -> Job:
    job.remote = job.remote or is_remote(job.location, job.description, remote_kw)
    if job.salary_min is None and job.salary_max is None:
        job.salary_min, job.salary_max = parse_salary_inr(job.description)
    job.deadline = job.deadline or parse_deadline(job.description)
    return job


def greenhouse(http: Http, token: str, remote_kw: list[str]) -> list[Job]:
    r = http.get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs", params={"content": "true"})
    r.raise_for_status()
    company = token
    try:
        meta = http.get(f"https://boards-api.greenhouse.io/v1/boards/{token}")
        if meta.ok:
            company = meta.json().get("name") or token
    except Exception:  # noqa: BLE001 - board name is cosmetic
        pass
    out = []
    for j in r.json().get("jobs", []):
        out.append(_finish(Job(
            source="greenhouse", platform="greenhouse", external_id=str(j["id"]),
            url=j.get("absolute_url", ""), apply_url=j.get("absolute_url", ""),
            title=j.get("title", ""), company=company,
            location=(j.get("location") or {}).get("name", ""),
            description=html_to_text(j.get("content")), posted_at=iso(j.get("updated_at")),
        ), remote_kw))
    return out


def lever(http: Http, token: str, remote_kw: list[str]) -> list[Job]:
    r = http.get(f"https://api.lever.co/v0/postings/{token}", params={"mode": "json"})
    r.raise_for_status()
    out = []
    for j in r.json():
        cats = j.get("categories") or {}
        desc = "\n".join(filter(None, [
            j.get("descriptionPlain", ""),
            *[f"{l.get('text', '')}\n{html_to_text(l.get('content'))}" for l in j.get("lists", [])],
            j.get("additionalPlain", ""),
        ]))
        sal = j.get("salaryRange") or {}
        job = Job(
            source="lever", platform="lever", external_id=j.get("id", ""),
            url=j.get("hostedUrl", ""), apply_url=j.get("applyUrl") or (j.get("hostedUrl", "") + "/apply"),
            title=j.get("text", ""), company=token, location=cats.get("location", "") or "",
            description=desc, posted_at=iso(j.get("createdAt")),
            remote=(j.get("workplaceType") == "remote"),
        )
        if sal.get("currency") == "INR":
            job.salary_min, job.salary_max = sal.get("min"), sal.get("max")
        out.append(_finish(job, remote_kw))
    return out


def ashby(http: Http, token: str, remote_kw: list[str]) -> list[Job]:
    r = http.get(f"https://api.ashbyhq.com/posting-api/job-board/{token}", params={"includeCompensation": "true"})
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        if not j.get("isListed", True):
            continue
        job = Job(
            source="ashby", platform="ashby", external_id=j.get("id", ""),
            url=j.get("jobUrl", ""), apply_url=j.get("applyUrl") or j.get("jobUrl", ""),
            title=j.get("title", ""), company=token, location=j.get("location", "") or "",
            description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml")),
            posted_at=iso(j.get("publishedAt")), remote=bool(j.get("isRemote")),
        )
        out.append(_finish(job, remote_kw))
    return out


def workable(http: Http, token: str, remote_kw: list[str]) -> list[Job]:
    r = http.get(f"https://apply.workable.com/api/v1/widget/accounts/{token}", params={"details": "true"})
    r.raise_for_status()
    data = r.json()
    company = data.get("name") or token
    out = []
    for j in data.get("jobs", []):
        loc = ", ".join(filter(None, [j.get("city"), j.get("state"), j.get("country")]))
        out.append(_finish(Job(
            source="workable", platform="workable", external_id=j.get("shortcode", ""),
            url=j.get("url", ""), apply_url=j.get("application_url") or j.get("url", ""),
            title=j.get("title", ""), company=company, location=loc,
            description=html_to_text(j.get("description")), posted_at=iso(j.get("published_on")),
            remote=bool(j.get("telecommuting")),
        ), remote_kw))
    return out


FETCHERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "workable": workable}


def fetch_all(http: Http, companies: dict, remote_kw: list[str]) -> tuple[list[Job], list[str]]:
    jobs, errors = [], []
    for ats, fn in FETCHERS.items():
        for token in companies.get(ats) or []:
            try:
                got = fn(http, token, remote_kw)
                jobs.extend(got)
                log.info("%s/%s: %d jobs", ats, token, len(got))
            except Exception as e:  # noqa: BLE001 - one bad board shouldn't stop the run
                errors.append(f"{ats}/{token}: {e}")
    return jobs, errors
