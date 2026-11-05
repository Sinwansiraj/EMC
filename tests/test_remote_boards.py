"""Offline tests for the Remote OK / We Work Remotely / Himalayas parsers (no network)."""
from job_agent.sources.feeds import detect_platform
from job_agent.sources.remote_boards import (himalayas_eligible, parse_himalayas, parse_remoteok,
                                             parse_wwr_rss, region_ok, restricted_elsewhere)

KW = ["data", "machine learning", "python", "llm", "support"]

REMOTEOK = [
    {"last_updated": 1, "legal": "API Terms of Service: Please link back to the URL on Remote OK"},
    {"id": "1001", "position": "Junior Data Analyst", "company": "Acme", "location": "Worldwide",
     "tags": ["data", "sql"], "description": "<p>SQL and Python dashboards.</p>", "date": "2026-11-03T10:00:00+00:00",
     "url": "https://remoteok.com/remote-jobs/1001", "salary_min": 40000, "salary_max": 60000},
    {"id": "1002", "position": "ML Engineer", "company": "Beta", "location": "United States",
     "tags": ["python"], "description": "Build models.", "url": "https://remoteok.com/remote-jobs/1002"},
    {"id": "1003", "position": "Python Developer", "company": "Gamma", "location": "Remote",
     "tags": ["python"], "description": "This role is US-only. Must be located in the United States.",
     "url": "https://remoteok.com/remote-jobs/1003"},
    {"id": "1004", "position": "Graphic Designer", "company": "Delta", "location": "Worldwide",
     "tags": ["design"], "description": "Figma work.", "url": "https://remoteok.com/remote-jobs/1004"},
]


def test_remoteok_parse_filters_region_and_keywords():
    jobs = parse_remoteok(REMOTEOK, KW)
    assert [j.external_id for j in jobs] == ["1001"]          # US, US-only, off-topic dropped; legal row skipped
    j = jobs[0]
    assert j.platform == "remoteok" and j.url == "https://remoteok.com/remote-jobs/1001"
    assert j.remote and j.posted_at == "2026-11-03" and j.salary_max is None   # USD not treated as INR
    assert j.extra["credit"] == "Remote OK"


WWR = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>WWR</title>
<item><title>Acme Corp: Customer Support Specialist</title><region>Anywhere in the World</region>
<category>Customer Support</category><type>Full-Time</type>
<description>&lt;p&gt;Help customers via Zendesk. Support SLAs.&lt;/p&gt;</description>
<pubDate>Tue, 03 Nov 2026 08:00:00 +0000</pubDate>
<guid>https://weworkremotely.com/remote-jobs/acme-support</guid>
<link>https://weworkremotely.com/remote-jobs/acme-support</link></item>
<item><title>Beta: Senior Python Engineer</title><region>USA Only</region>
<description>Python.</description><pubDate>Tue, 03 Nov 2026 08:00:00 +0000</pubDate>
<link>https://weworkremotely.com/remote-jobs/beta-python</link></item>
</channel></rss>"""


def test_wwr_rss_parse():
    jobs = parse_wwr_rss(WWR, KW)
    assert len(jobs) == 1
    j = jobs[0]
    assert (j.company, j.title) == ("Acme Corp", "Customer Support Specialist")
    assert j.location == "Remote (Anywhere in the World)" and j.posted_at == "2026-11-03"
    assert "Zendesk" in j.description and j.platform == "weworkremotely"


HIMA = {"totalCount": 4, "jobs": [
    {"title": "AI Engineer", "companyName": "Lemon", "applicationLink": "https://himalayas.app/companies/lemon/jobs/ai-engineer",
     "guid": "https://himalayas.app/companies/lemon/jobs/ai-engineer", "locationRestrictions": [],
     "timezoneRestrictions": [], "seniority": ["Mid-level"], "description": "<p>LLM apps in Python</p>",
     "pubDate": 1762156800, "expiryDate": 1767225600, "currency": "INR", "minSalary": 50000, "maxSalary": 80000,
     "salaryPeriod": "monthly", "employmentType": "Full Time"},
    {"title": "Data Analyst", "companyName": "Euro", "applicationLink": "https://himalayas.app/companies/euro/jobs/da",
     "locationRestrictions": [{"alpha2": "DE", "name": "Germany", "slug": "germany"}], "timezoneRestrictions": []},
    {"title": "Data Scientist", "companyName": "Asia", "applicationLink": "https://himalayas.app/companies/asia/jobs/ds",
     "locationRestrictions": [{"alpha2": "IN", "name": "India", "slug": "india"}], "timezoneRestrictions": ["-5", "-8"]},
    {"title": "Staff ML Engineer", "companyName": "Big", "applicationLink": "https://himalayas.app/companies/big/jobs/ml",
     "locationRestrictions": [], "timezoneRestrictions": [], "seniority": ["Senior", "Executive"]},
]}


def test_himalayas_parse_eligibility_salary_seniority():
    jobs = parse_himalayas(HIMA, ["Senior", "Director", "Executive"])
    assert [j.company for j in jobs] == ["Lemon"]   # Germany-only, wrong timezone, senior-only dropped
    j = jobs[0]
    assert j.apply_url == "https://himalayas.app/companies/lemon/jobs/ai-engineer"
    assert (j.salary_min, j.salary_max) == (600000, 960000)     # monthly INR x 12
    assert j.location == "Remote (Worldwide)" and j.posted_at and j.deadline


def test_himalayas_timezone_formats():
    base = {"locationRestrictions": [{"name": "India", "alpha2": "IN"}]}
    assert himalayas_eligible({**base, "timezoneRestrictions": ["5.5"]})
    assert himalayas_eligible({**base, "timezoneRestrictions": ["UTC+05:30", "UTC+8"]})
    assert not himalayas_eligible({**base, "timezoneRestrictions": ["+1", "+2"]})


def test_region_helpers_and_platforms():
    assert region_ok("Anywhere in the World") and region_ok("") and region_ok("APAC")
    assert not region_ok("USA Only") and not region_ok("Europe")
    assert restricted_elsewhere("Candidates must reside in the US.")
    assert not restricted_elsewhere("We hire across 40 countries.")
    assert detect_platform("https://himalayas.app/companies/x/jobs/y") == "himalayas"
    assert detect_platform("https://remoteok.com/remote-jobs/1") == "remoteok"
    assert detect_platform("https://weworkremotely.com/remote-jobs/x") == "weworkremotely"
