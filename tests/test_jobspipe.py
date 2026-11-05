"""Offline tests for the JobsPipe source: record mapping, search building, budget and delta cursor."""
import json

from job_agent.sources import jobspipe

ROW = {"id": "3912345", "job_title": "Data Analyst", "company": "Acme India",
       "url": "https://www.linkedin.com/jobs/view/3912345/", "location": "Chennai, Tamil Nadu, India",
       "country_code": "IN", "remote": False, "description": "<p>SQL, Power BI dashboards</p>",
       "salary_currency": "INR", "min_annual_salary": 500000, "max_annual_salary": 700000,
       "date_posted": "2026-11-03T09:00:00+00:00", "expires_at": None, "sources": [{"provider": "linkedin"}]}
REMOTE_ROW = {**ROW, "id": "gh-1", "url": "https://boards.greenhouse.io/x/jobs/1", "location": "India",
              "remote": True, "salary_currency": "USD", "sources": [{"provider": "greenhouse"}]}


def test_to_job_mapping():
    j = jobspipe.to_job(ROW)
    assert j.platform == "linkedin" and j.external_id == "3912345"     # LinkedIn stays assist-only
    assert (j.salary_min, j.salary_max) == (500000, 700000) and j.posted_at == "2026-11-03"
    r = jobspipe.to_job(REMOTE_ROW)
    assert r.platform == "greenhouse" and r.remote and r.location == "Remote (India)" and r.salary_max is None
    assert jobspipe.to_job({"job_title": "x"}) is None


def test_build_searches():
    cfg = {"cities": ["Chennai"], "remote": True, "country_code": "IN", "max_age_days": 3,
           "exclude_title_words": ["senior"], "max_ghost_score": 60}
    s = jobspipe.build_searches(cfg, ["data analyst"])
    assert set(s) == {"cities", "remote"}
    assert s["cities"]["city_or"] == ["Chennai"] and "remote" not in s["cities"]
    assert s["remote"]["remote"] is True and s["remote"]["job_country_code_or"] == ["IN"]


class FakeResp:
    def __init__(self, data, code=200):
        self._d, self.status_code, self.ok, self.text = data, code, code < 400, json.dumps(data)

    def json(self):
        return self._d


class FakeSession:
    def __init__(self, pages):
        self.pages, self.bodies = pages, []

    def post(self, url, headers=None, json=None, timeout=None):
        self.bodies.append(json)
        return self.pages.pop(0)


class FakeHttp:
    def __init__(self, pages):
        self.s, self.timeout = FakeSession(pages), 5


class FakeDB:
    def __init__(self):
        self.meta = {}

    def get_meta(self, k, default=None):
        return self.meta.get(k, default)

    def set_meta(self, k, v):
        self.meta[k] = v


def page(rows, charged, remaining, next_cursor=None, delta=None):
    return FakeResp({"metadata": {"credits_charged": charged, "credits_remaining": remaining,
                                  "next_cursor": next_cursor, "next_delta_cursor": delta}, "data": rows})


def test_fetch_saves_delta_cursor_and_uses_it(monkeypatch):
    monkeypatch.setenv("JOBSPIPE_API_KEY", "jp_test")
    monkeypatch.setattr(jobspipe.time, "sleep", lambda s: None)
    cfg = {"remote": True, "max_credits_per_run": 60, "stop_when_credits_below": 50}
    db = FakeDB()
    http = FakeHttp([page([ROW], 1, 999, next_cursor="c2"), page([REMOTE_ROW], 1, 998, delta="d1")])
    jobs, errs, stats = jobspipe.fetch(http, db, {"profiles": {}}, cfg)
    assert len(jobs) == 2 and not errs and stats["credits_charged"] == 2
    assert http.s.bodies[1]["cursor"] == "c2"
    assert json.loads(db.meta["jobspipe_delta:remote"])["cursor"] == "d1"
    http2 = FakeHttp([page([], 0, 998, delta="d2")])
    jobspipe.fetch(http2, db, {"profiles": {}}, cfg)
    assert http2.s.bodies[0]["delta_cursor"] == "d1"           # second run only asks for new postings


def test_fetch_respects_budget_and_reserve(monkeypatch):
    monkeypatch.setenv("JOBSPIPE_API_KEY", "jp_test")
    monkeypatch.setattr(jobspipe.time, "sleep", lambda s: None)
    db = FakeDB()
    cfg = {"remote": True, "max_credits_per_run": 30, "stop_when_credits_below": 50}
    http = FakeHttp([page([ROW], 25, 900, next_cursor="c2")])
    jobs, errs, stats = jobspipe.fetch(http, db, {"profiles": {}}, cfg)
    assert len(http.s.bodies) == 1 and "budget" in errs[0] and "jobspipe_delta:remote" not in db.meta
    http = FakeHttp([page([ROW], 25, 60, next_cursor="c2")])
    jobs, errs, stats = jobspipe.fetch(http, db, {"profiles": {}}, {**cfg, "max_credits_per_run": 500})
    assert len(http.s.bodies) == 1 and "reserve" in errs[0]


def test_fetch_without_key(monkeypatch):
    monkeypatch.delenv("JOBSPIPE_API_KEY", raising=False)
    jobs, errs, _ = jobspipe.fetch(FakeHttp([]), FakeDB(), {}, {})
    assert jobs == [] and "not set" in errs[0]
