import json
from pathlib import Path

import pytest
import yaml

from job_agent import matcher, prepare
from job_agent.answers import Answerer, choose_option
from job_agent.config import load_config
from job_agent.db import DB
from job_agent.discover import store
from job_agent.sources.base import Job, parse_deadline, parse_salary_inr
from job_agent.sources.feeds import parse_alert_email
from job_agent.tailor import invention_guard, prepare_documents

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).parent / "fixtures"
CFG = load_config(ROOT / "config" / "config.yaml")
PROFILE = yaml.safe_load((ROOT / "private" / "profile.yaml").read_text(encoding="utf-8"))
RKW = CFG["search"]["locations"]["remote_keywords"]

DA_JD = """We are hiring a Data Analyst in Chennai. You will build Power BI dashboards and write SQL.
Requirements: 0-2 years of experience. Strong Python (pandas, numpy) and SQL. Excel. Communication skills.
Good to have: Tableau, AWS. Salary: 5 - 7 LPA. Apply by 30 November 2026."""


AI_JD = """We're hiring an AI Application Engineer in Bengaluru to build end-to-end LLM features. You will
integrate OpenAI and Claude APIs into Python/FastAPI services, automate workflows, write REST APIs, deploy with
Docker and CI/CD, and prototype agents. 0-2 years of experience. Salary 6 - 9 LPA."""

PROMPT_JD = """Prompt Engineer (Remote, India). Design and iterate prompts for large language models (GPT, Claude),
build evaluation sets to measure output quality and hallucination, enforce structured outputs with JSON schema and
function calling, and improve RAG retrieval. Python required. 1+ years of experience."""

BI_SALES_JD = """Business Intelligence Analyst - Field Sales. Meet clients daily, generate leads, close deals, hit
monthly sales targets, travel across the territory, maintain relationships with distributors and retailers.
Two-wheeler mandatory. Fresh graduates welcome. Attractive incentives on top of fixed pay."""


def job(**kw):
    base = dict(source="test", platform="greenhouse", url="https://x/1", title="Data Analyst", company="Acme",
                location="Chennai, India", description=DA_JD)
    base.update(kw)
    return Job(**base)


def fresh_db(tmp_path):
    return DB(tmp_path / "t.db")


# ---------------------------------------------------------------- parsing
def test_salary_and_deadline():
    assert parse_salary_inr("CTC 5 - 7 LPA") == (500000, 700000)
    assert parse_salary_inr("₹30,000 - ₹40,000 per month") == (360000, 480000)
    assert parse_salary_inr("up to 4 LPA") == (None, 400000)
    assert parse_deadline("Apply by 30 November 2026.") == "2026-11-30"


def test_alert_email_parsing():
    jobs = parse_alert_email((FIX / "linkedin_alert.html").read_text(encoding="utf-8"), RKW)
    by = {j.title: j for j in jobs}
    assert by["Data Analyst"].company == "Acme Analytics"
    assert "Bengaluru" in by["Data Analyst"].location
    assert by["Data Analyst"].url == "https://www.linkedin.com/jobs/view/4012345678/"
    assert by["Data Analyst"].platform == "linkedin" and by["Data Analyst"].partial
    assert by["Python Developer"].company == "Zeta Tech"
    assert by["Python Developer"].platform == "naukri"


# ---------------------------------------------------------------- dedup
def test_dedup_merges_same_role_from_two_sources(tmp_path):
    db = fresh_db(tmp_path)
    s1 = store(db, [job(), job(url="https://www.linkedin.com/jobs/view/9/", source="linkedin_alert",
                                  company="Acme Pvt Ltd", title="Data Analyst (Remote)")])
    assert s1["new"] == 1 and s1["duplicates_merged"] == 1
    s2 = store(db, [job()])
    assert s2["new"] == 0
    also = json.loads(db.one("SELECT also_seen_at FROM jobs")["also_seen_at"])
    assert "https://www.linkedin.com/jobs/view/9/" in also


# ---------------------------------------------------------------- scoring
def score(**kw):
    j = job(**kw)
    return matcher.score_job({**j.__dict__, "remote": j.remote}, PROFILE, CFG)


def test_good_match_scores_high():
    r = score()
    assert r["filter_reason"] is None
    assert r["family"] == "data_analyst"
    assert r["score"] >= 70, r


def test_filters():
    assert score(title="Senior Data Scientist")["filter_reason"] == "senior-level title"
    assert "location" in score(location="Pune, India")["filter_reason"]
    assert "years" in score(description=DA_JD.replace("0-2 years", "5+ years"))["filter_reason"]
    assert "salary" in score(description=DA_JD.replace("5 - 7 LPA", "3 - 4 LPA"))["filter_reason"]
    assert score(title="Marketing Executive")["filter_reason"] == "title not in target roles"


def test_support_manager_uses_hospitality_years():
    jd = "Customer Support Manager. 4+ years of experience managing a support team, SLAs, Zendesk, root cause analysis."
    r = score(title="Customer Support Manager", description=jd * 3)
    assert r["filter_reason"] is None and r["family"] == "customer_support_mgmt"
    assert r["detail"]["experience"] == 15


def test_missing_requirements_listed():
    jd = DA_JD + " Must know Tableau and Spark. Requirements include Spark and Airflow. B.Tech in Computer Science."
    r = score(description=jd.replace("Good to have", "Also"))
    joined = " ".join(r["missing"])
    assert "spark" in joined and "degree" in joined


# ---------------------------------------------------------------- answers
@pytest.mark.parametrize("q,expected,conf", [
    ("First Name *", "Mohammed", "exact"),
    ("What is your preferred name?", "Sinwan Siraj", "exact"),
    ("Email address", "sinwanmohammed022@gmail.com", "exact"),
    ("Expected CTC (INR per annum)", "550000", "exact"),
    ("Expected monthly salary", "45833", "derived"),
    ("What is your notice period?", "0", "exact"),
    ("How many years of experience do you have with Python?", "1", "exact"),
    ("Total work experience", "9", "exact"),
    ("Relevant experience in data science (years)", "1.2", "exact"),
    ("Will you now or in the future require visa sponsorship?", "No", "exact"),
    ("Are you legally authorized to work in India?", "Yes", "exact"),
    ("Have you used Power BI?", "No", "exact"),
    ("How many years of experience do you have with Excel?", "0", "exact"),
    ("Date of birth", "1996-05-06", "exact"),
    ("Pincode", "641301", "exact"),
    ("Marital status", "Single", "exact"),
    ("Do you have experience with Kubernetes?", "No", "review"),
    ("Why do you want to work at Acme?", "", "unknown"),
    ("What is your 12th school percentage?", "", "unknown"),
    ("Graduation percentage", "58%", "exact"),
    ("How many years of experience do you have with Java?", "0", "review"),
    ("How many years of experience do you have in customer support?", "5", "exact"),
    ("GitHub profile URL", "https://github.com/Sinwansiraj", "exact"),
    ("Preferred location", "Coimbatore, Chennai, Bengaluru, Remote", "exact"),
    ("Are you related to any current employee?", "No", "exact"),
    ("PAN number", "", "unknown"),
    ("Do you have experience related to data analysis?", "", "unknown"),
])
def test_answers(q, expected, conf):
    a = Answerer(PROFILE).answer(q)
    assert (a.value, a.confidence) == (expected, conf), (q, a)


def test_choose_option():
    assert choose_option("0", ["Select...", "Immediate", "15 days", "1 month"]) == "Immediate"
    assert choose_option("No", ["Yes", "No"]) == "No"
    assert choose_option("1.2", ["0-1 years", "1-3 years", "3+ years"]) == "1-3 years"
    assert choose_option("9", ["0-2", "2-5", "5+ years"]) == "5+ years"
    assert choose_option("Maybe", ["Yes", "No"]) is None


# ---------------------------------------------------------------- tailoring
def test_prepare_documents_no_invention(tmp_path):
    j = {**job().__dict__, "role_family": "data_analyst", "id": 1}
    out = prepare_documents(j, PROFILE, CFG, tmp_path)
    assert out["guard_violations"] == []
    assert Path(out["resume_docx"]).exists() and Path(out["cover_path"]).exists()
    assert "sql" in out["skills"][:4]
    assert not {"power bi", "excel", "mlflow", "shap"} & set(out["skills"])
    assert "Acme" in out["cover_text"]


def test_guard_catches_inflation():
    bad = "Data scientist with 5 years of Kubernetes and Spark experience who improved revenue by 37%."
    v = invention_guard(bad, PROFILE)
    assert any("kubernetes" in x for x in v) and any("spark" in x for x in v) and any("37%" in x for x in v)


def test_prepare_respects_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare, "PRIVATE", tmp_path)
    db = fresh_db(tmp_path)
    store(db, [job(), job(title="AI Application Engineer", url="https://x/2", description=AI_JD)])
    matcher.run(db, PROFILE, CFG)
    st = prepare.run(db, PROFILE, CFG)
    assert st["prepared"] == 2
    a = db.one("SELECT * FROM applications WHERE job_id=1")
    assert a["selection_reason"].startswith("score") and a["resume_version"].startswith("data_analyst-")
    # same company + same title discovered again from a new source does not re-queue
    store(db, [job(url="https://y/9", company="ACME Ltd")])
    assert prepare.run(db, PROFILE, CFG)["prepared"] == 0


# ---------------------------------------------------------------- scoring profiles
def test_related_title_kept_when_responsibilities_match():
    r = score(title="Business Intelligence Analyst")          # DA_JD: SQL, dashboards, reports, KPIs
    assert r["filter_reason"] is None and r["family"] == "data_analyst"
    assert r["detail"]["match"] == "related"


def test_related_title_dropped_when_work_differs():
    r = score(title="Business Intelligence Analyst", description=BI_SALES_JD)
    assert r["filter_reason"] and "responsibilities" in r["filter_reason"]


def test_prompt_engineer_profile():
    r = score(title="Prompt Engineer", location="Remote", description=PROMPT_JD)
    assert r["filter_reason"] is None and r["family"] == "prompt_engineer"
    assert {"llm", "structured outputs", "rag"} <= set(r["detail"]["priority_matched"])
    assert r["score"] >= 70, r


def test_ai_builder_related_title():
    r = score(title="Python Developer", location="Bengaluru", description=AI_JD)
    assert r["filter_reason"] is None and r["family"] == "ai_builder"


def test_best_profile_wins():
    # "AI Engineer" is primary for AI & ML Engineer; an LLM-app description also fits AI Builder.
    r = score(title="Junior AI Engineer", location="Chennai", description=AI_JD)
    assert r["filter_reason"] is None
    assert r["family"] in ("ai_ml_engineer", "ai_builder")


def test_evidence_skills_answers():
    a = Answerer(PROFILE)
    assert a.answer("Do you have experience with Docker?").value == "Yes"
    r = a.answer("How many years of experience do you have with Docker?")
    assert (r.value, r.confidence) == ("1", "review")
    assert (a.answer("Have you used MLflow?").value, a.answer("Have you used SHAP?").value) == ("No", "No")


def test_unconfirmed_projects_never_used(tmp_path):
    j = {**job(description=DA_JD + " SHAP explainability customer churn").__dict__, "role_family": "data_scientist", "id": 2}
    out = prepare_documents(j, PROFILE, CFG, tmp_path)
    assert "B2B Customer Health Scoring Engine" not in out["projects"]
    assert out["guard_violations"] == []
