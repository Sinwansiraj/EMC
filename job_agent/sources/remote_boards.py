"""Remote-first job boards with official public feeds: Remote OK (JSON API), We Work Remotely (RSS)
and Himalayas (JSON API).

All three publish these feeds for automated use, so no pages are crawled. Their terms ask for the
original posting link to be kept and the board credited, so every job stores the board's own URL
(and Himalayas' `applicationLink`, which its terms require for applying). Applying stays manual
("assist" in config.yaml) because the real application page sits behind each board.

Fetching and parsing are separate so the parsers can be tested offline with fixtures.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from .base import Http, Job, html_to_text, iso, parse_deadline

# Region text that means someone living in India can apply.
OK_REGIONS = ("india", "worldwide", "anywhere", "asia", "apac", "global", "earth", "no restriction")

# Description wording that limits a "remote" job to another country or region.
_RESTRICTED = re.compile(
    r"(?i)\b(?:us|u\.s\.?|usa|united states|eu|europe|uk|canada|latam|north america|americas)"
    r"[- ](?:only|based|residents?|citizens?)\b"
    r"|\bmust (?:be|reside|live)(?: located| based)? in (?:the )?"
    r"(?:us|u\.s\.?|usa|united states|europe|eu|uk|canada|north america)\b"
    r"|\bauthori[sz]ed to work in (?:the )?(?:us|u\.s\.?|usa|united states|uk|canada)\b")


def region_ok(region: str) -> bool:
    r = (region or "").strip().lower()
    if not r or r in ("remote", "remote job", "remote jobs"):
        return True          # unstated - description check decides
    return any(k in r for k in OK_REGIONS)


def restricted_elsewhere(text: str) -> bool:
    return bool(_RESTRICTED.search((text or "")[:3000]))


# ---------------------------------------------------------------- Remote OK
REMOTEOK_API = "https://remoteok.com/api"


def parse_remoteok(data: list, keywords: list[str] | None = None) -> list[Job]:
    """data = the API's JSON array. Element 0 is a legal/metadata notice, not a job."""
    out = []
    kws = [k.lower() for k in (keywords or [])]
    for j in data:
        if not isinstance(j, dict) or not j.get("position") or not j.get("id"):
            continue
        loc = (j.get("location") or "").strip()
        desc = html_to_text(j.get("description"))
        if not region_ok(loc) or restricted_elsewhere(desc):
            continue
        tags = [str(t).lower() for t in (j.get("tags") or [])]
        if kws:
            hay = " ".join([j["position"].lower(), " ".join(tags), desc[:1500].lower()])
            if not any(k in hay for k in kws):
                continue
        url = j.get("url") or f"https://remoteok.com/remote-jobs/{j['id']}"
        out.append(Job(
            source="remoteok", platform="remoteok", external_id=str(j["id"]), url=url, apply_url=url,
            title=j["position"].strip(), company=(j.get("company") or "").strip(),
            location=f"Remote ({loc})" if loc else "Remote", description=desc, remote=True,
            posted_at=iso(j.get("date") or j.get("epoch")), deadline=parse_deadline(desc),
            extra={"tags": tags, "salary_usd": [j.get("salary_min"), j.get("salary_max")],
                   "credit": "Remote OK"},
        ))
    return out


def remoteok(http: Http, cfg: dict) -> list[Job]:
    """The feed is the newest ~100 postings (about a week) with no search or working tag filter,
    so one request per daily run is all it takes; keyword filtering happens here."""
    r = http.get(REMOTEOK_API)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code}")
    return parse_remoteok(r.json(), cfg.get("keywords"))


# ---------------------------------------------------------------- We Work Remotely
WWR_FEED = "https://weworkremotely.com/categories/{slug}.rss"
WWR_ALL = "https://weworkremotely.com/remote-jobs.rss"


def _t(item: ET.Element, tag: str) -> str:
    el = item.find(tag)
    return (el.text or "").strip() if el is not None and el.text else ""


def parse_wwr_rss(xml_text: str, keywords: list[str] | None = None) -> list[Job]:
    out = []
    kws = [k.lower() for k in (keywords or [])]
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):
        raw_title, link = _t(item, "title"), _t(item, "link")
        if not raw_title or not link:
            continue
        company, sep, title = raw_title.partition(":")
        if not sep:
            company, title = "", raw_title
        region = _t(item, "region") or _t(item, "country")
        desc = html_to_text(_t(item, "description"))
        if not region_ok(region) or restricted_elsewhere(desc):
            continue
        if kws and not any(k in f"{title} {desc[:1500]}".lower() for k in kws):
            continue
        try:
            posted = parsedate_to_datetime(_t(item, "pubDate")).date().isoformat()
        except (TypeError, ValueError):
            posted = None
        out.append(Job(
            source="weworkremotely", platform="weworkremotely", external_id=_t(item, "guid") or link,
            url=link, apply_url=link, title=title.strip(), company=company.strip(),
            location=f"Remote ({region})" if region else "Remote", description=desc, remote=True,
            posted_at=posted, deadline=parse_deadline(desc),
            extra={"category": _t(item, "category"), "type": _t(item, "type"), "credit": "We Work Remotely"},
        ))
    return out


def weworkremotely(http: Http, cfg: dict) -> tuple[list[Job], list[str]]:
    jobs: dict[str, Job] = {}
    errors = []
    urls = ([WWR_ALL] if cfg.get("include_all_jobs_feed", True) else []) + \
           [WWR_FEED.format(slug=s) for s in cfg.get("categories", [])]
    for url in urls:
        r = http.get(url)
        if not r.ok:
            errors.append(f"weworkremotely {url.rsplit('/', 1)[-1]}: HTTP {r.status_code}")
            continue
        try:
            for j in parse_wwr_rss(r.text, cfg.get("keywords")):
                jobs.setdefault(j.url, j)
        except ET.ParseError as e:
            errors.append(f"weworkremotely {url.rsplit('/', 1)[-1]}: bad RSS ({e})")
    return list(jobs.values()), errors


# ---------------------------------------------------------------- Himalayas
HIMALAYAS_SEARCH = "https://himalayas.app/jobs/api/search"
_PERIOD_X = {"hourly": 2080, "weekly": 52, "fortnightly": 26, "monthly": 12, "annual": 1, "yearly": 1}


def _country_names(restrictions) -> list[str]:
    names = []
    for r in restrictions or []:
        if isinstance(r, dict):
            names += [str(r.get(k, "")).lower() for k in ("name", "alpha2", "slug")]
        else:
            names.append(str(r).lower())
    return names


def _tz_offsets(values) -> list[float]:
    out = []
    for v in values or []:
        m = re.search(r"([+-]?)(\d{1,2})(?:[:.](\d{1,2}))?", str(v))
        if not m:
            continue
        h, frac = int(m.group(2)), m.group(3)
        if frac is None:
            mins = 0
        elif ":" in str(v):
            mins = int(frac)
        else:                                   # decimal form, e.g. 5.5
            mins = round(float("0." + frac) * 60)
        val = h + mins / 60
        out.append(-val if m.group(1) == "-" else val)
    return out


def himalayas_eligible(job: dict, country: str = "india", alpha2: str = "in", tz: float = 5.5) -> bool:
    """Himalayas' rule: open to a country when locationRestrictions is empty or includes it, and
    timezoneRestrictions is empty or includes the country's offset (India: UTC+5:30)."""
    names = _country_names(job.get("locationRestrictions"))
    if names and country not in names and alpha2 not in names:
        return False
    offsets = _tz_offsets(job.get("timezoneRestrictions"))
    if job.get("timezoneRestrictions") and offsets and not any(abs(o - tz) < 0.01 for o in offsets):
        return False
    return True


def parse_himalayas(data: dict, skip_seniority: list[str] | None = None) -> list[Job]:
    out = []
    skip = {s.lower() for s in (skip_seniority or [])}
    for j in data.get("jobs", []):
        if not j.get("title") or not j.get("applicationLink"):
            continue
        if not himalayas_eligible(j):
            continue
        sen = [str(s) for s in (j.get("seniority") or [])]
        if sen and skip and all(s.lower() in skip for s in sen):
            continue
        smin = smax = None
        if (j.get("currency") or "").upper() == "INR":
            x = _PERIOD_X.get((j.get("salaryPeriod") or "annual").lower(), 1)
            smin = int(j["minSalary"] * x) if j.get("minSalary") else None
            smax = int(j["maxSalary"] * x) if j.get("maxSalary") else None
        restr = [n for n in (r.get("name") if isinstance(r, dict) else r
                             for r in (j.get("locationRestrictions") or [])) if n]
        link = j["applicationLink"]
        out.append(Job(
            source="himalayas", platform="himalayas", external_id=str(j.get("guid") or link),
            url=link, apply_url=link,            # Himalayas terms: apply through applicationLink
            title=j["title"].strip(), company=(j.get("companyName") or "").strip(),
            location="Remote (" + (", ".join(restr[:4]) if restr else "Worldwide") + ")",
            description=html_to_text(j.get("description")) or (j.get("excerpt") or ""), remote=True,
            salary_min=smin, salary_max=smax, posted_at=iso(j.get("pubDate")),
            deadline=iso(j.get("expiryDate")),
            extra={"seniority": sen, "employment_type": j.get("employmentType"),
                   "timezones": j.get("timezoneRestrictions") or [], "credit": "Himalayas",
                   "salary": [j.get("currency"), j.get("minSalary"), j.get("maxSalary"), j.get("salaryPeriod")]},
        ))
    return out


def himalayas(http: Http, cfg: dict) -> tuple[list[Job], list[str]]:
    """One search per query, restricted to jobs open to India. The data refreshes daily, so a
    daily run is enough. Optional free key (HIMALAYAS_API_KEY in private/.env) raises rate limits."""
    jobs: dict[str, Job] = {}
    errors = []
    key = os.environ.get("HIMALAYAS_API_KEY")
    headers = {"Authorization": f"Bearer {key}"} if key else None
    for q in cfg.get("queries", []):
        for page in range(1, int(cfg.get("max_pages", 2)) + 1):
            r = http.get(HIMALAYAS_SEARCH, headers=headers,
                         params={"q": q, "country": cfg.get("country", "India"), "sort": "recent", "page": page})
            if r.status_code == 429:
                errors.append("himalayas: rate limited (429) - stopped early; a free API key raises the limit")
                return list(jobs.values()), errors
            if not r.ok:
                errors.append(f"himalayas '{q}': HTTP {r.status_code}")
                break
            data = r.json()
            got = parse_himalayas(data, cfg.get("skip_seniority"))
            for j in got:
                jobs.setdefault(j.external_id, j)
            if len(data.get("jobs", [])) < 20:
                break
    return list(jobs.values()), errors
