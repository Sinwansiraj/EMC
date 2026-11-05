"""Score each job against your real profile and explain the score."""
from __future__ import annotations

import json
import re

from .db import DB
from .sources.base import parse_salary_inr

# canonical skill -> regex alternatives found in job descriptions
SKILL_VOCAB: dict[str, str] = {
    "python": r"python",
    "sql": r"\bsql\b|mysql|t-sql|pl/sql",
    "postgresql": r"postgres(?:ql)?",
    "pandas": r"pandas",
    "numpy": r"numpy",
    "scikit-learn": r"scikit[- ]?learn|sklearn",
    "xgboost": r"xgboost|gradient boost",
    "machine learning": r"machine learning|\bml\b",
    "deep learning": r"deep learning|neural network",
    "nlp": r"\bnlp\b|natural language",
    "llm": r"\bllms?\b|large language model|genai|generative ai|\bgpt",
    "pytorch": r"pytorch",
    "tensorflow": r"tensorflow|keras",
    "distilbert": r"bert|transformers|hugging ?face",
    "power bi": r"power ?bi",
    "tableau": r"tableau",
    "excel": r"\bexcel\b|spreadsheets?",
    "statistics": r"statistic|hypothesis test|a/b test",
    "fastapi": r"fastapi",
    "flask": r"\bflask\b",
    "django": r"django",
    "streamlit": r"streamlit",
    "rest apis": r"rest(?:ful)? api|\bapis?\b",
    "git": r"\bgit\b|github|gitlab|version control",
    "aws": r"\baws\b|amazon web services|\bec2\b|\bs3\b|sagemaker",
    "azure": r"\bazure\b",
    "gcp": r"\bgcp\b|google cloud|bigquery",
    "docker": r"docker|container",
    "kubernetes": r"kubernetes|\bk8s\b",
    "mlflow": r"mlflow",
    "airflow": r"airflow",
    "spark": r"spark|pyspark|databricks",
    "shap": r"\bshap\b|explainab",
    "playwright": r"playwright",
    "web scraping": r"scrap(?:ing|er)",
    "data visualization": r"visuali[sz]ation|dashboards?",
    "etl": r"\betl\b|data pipelines?",
    "linux": r"linux|unix|bash",
    "javascript": r"javascript|typescript|node\.?js",
    "incident response": r"incident (?:response|management)|on-?call|production issues?",
    "root-cause analysis": r"root[- ]cause|\brca\b",
    "troubleshooting": r"troubleshoot|debug",
    "documentation": r"documentation|runbooks?|knowledge base",
    "customer support": r"customer support|customer service|helpdesk|help desk|ticketing|zendesk|freshdesk",
    "customer success": r"customer success|account management|retention|churn",
    "team leadership": r"team lead|people management|managing a team|lead a team|supervis",
    "crm": r"\bcrm\b|salesforce|hubspot",
    "sla management": r"\bslas?\b|service level",
    "communication": r"communication skills|written and verbal|excellent communication",
    # --- added for the six scoring profiles
    "model evaluation": r"model (evaluation|validation|performance|metrics)|cross[- ]validation|roc[- ]?auc|precision|recall|f1",
    "feature engineering": r"feature (engineering|selection|extraction)",
    "dashboards": r"dashboards?",
    "reporting": r"\breport(s|ing)\b|\bmis\b",
    "kpis": r"\bkpis?\b|business metrics|key metrics",
    "escalations": r"escalat",
    "operations": r"\boperations\b|process improvement|workflow",
    "csat": r"csat|\bnps\b|customer satisfaction",
    "prompt engineering": r"prompt (engineering|design|writing|crafting)|prompting",
    "prompt evaluation": r"prompt (evaluation|testing|optimi[sz]ation)|evals?\b|llm evaluation|eval(uation)? (sets?|framework)",
    "structured outputs": r"structured outputs?|json (mode|schema|output)|function calling|tool (use|calling)",
    "rag": r"\brag\b|retrieval[- ]augmented|vector (db|database|store|search)|embeddings?",
    "anthropic api": r"anthropic|claude",
    "openai api": r"openai|chatgpt|gpt-?4|gpt-?3",
    "evaluation": r"evaluat",
    "automation": r"automat(e|ion|ing)",
    "mcp": r"\bmcp\b|model context protocol",
    "react": r"\breact(\.js|js)?\b",
    "typescript": r"typescript",
    "ml pipelines": r"(ml|machine learning|training|data) pipelines?",
    "model serving": r"model (serving|deployment)|inference|serve models",
    "deployment": r"deploy(ment|ing)?",
    "ci/cd": r"ci/cd|ci-cd|continuous (integration|delivery|deployment)|github actions|jenkins",
    "transformers": r"transformers|hugging ?face|bert",
    "testing": r"\bpytest\b|unit tests?|test automation|testing",
    "mlops": r"mlops|model monitoring|drift",
    "selenium": r"selenium",
    "mysql": r"mysql",
    "redis": r"\bredis\b",
    "lightgbm": r"lightgbm",
    "agents": r"\bagents?\b|agentic|multi-agent",
}

# profile skill / tag names -> canonical vocab names
ALIASES = {
    "scikit-learn": "scikit-learn", "github": "git", "deep learning": "deep learning",
    "operations management": "team leadership", "stakeholder management": "communication",
    "customer service": "customer support", "genai": "llm", "ai": "llm", "llm": "llm",
    "web scraping": "web scraping", "automation": "playwright", "data pipelines": "etl",
    "analytics": "data visualization", "mlops": "mlflow", "api": "rest apis", "saas": "troubleshooting",
    "authentication": "troubleshooting", "smoke testing": "troubleshooting", "explainability": "shap",
    "churn": "customer success", "customer success": "customer success",
}

PREFERRED_MARKERS = re.compile(r"(?i)(nice to have|good to have|preferred|bonus|plus if|would be a plus|desirable)")
YEARS_RE = re.compile(r"(?i)(\d{1,2})\s*(?:\+|plus)?\s*(?:-|–|to)?\s*(\d{1,2})?\s*\+?\s*(?:years?|yrs?)(?:'|’)?\s*(?:of)?\s*(?:\w+\s){0,4}?(?:experience|exp\b)")
GENERIC_LOC = re.compile(r"(?i)\bindia\b|\bin\b|multiple|locations?|pan|anywhere|hybrid|on-?site|office|[^a-z]+")
DEGREE_RE = re.compile(r"(?i)\b(b\.?\s?tech|b\.?e\b|m\.?tech|computer science|cs degree|engineering degree|degree in (?:computer|statistics|mathematics|engineering))")


def profile_skills(profile: dict) -> set[str]:
    have = set()
    names = list(profile.get("skills", {}).keys()) + list(profile.get("skills_evidence") or [])
    for p in profile.get("projects", []):
        names += p.get("tags", [])
    for r in profile.get("experience", {}).get("roles", []):
        names += r.get("tags", [])
    blocked = {s.lower() for s in profile.get("skills_not_have") or []}
    for n in names:
        n = n.lower().strip()
        if n in blocked:
            continue
        if n in SKILL_VOCAB:
            have.add(n)
        if n in ALIASES:
            have.add(ALIASES[n])
    return have


def extract_skills(text: str) -> tuple[set[str], set[str]]:
    """Return (required, preferred) canonical skills mentioned in a description."""
    if not text:
        return set(), set()
    m = PREFERRED_MARKERS.search(text)
    req_text, pref_text = (text[:m.start()], text[m.start():]) if m and m.start() > 200 else (text, "")
    req = {k for k, pat in SKILL_VOCAB.items() if re.search(pat, req_text, re.I)}
    pref = {k for k, pat in SKILL_VOCAB.items() if re.search(pat, pref_text, re.I)} - req
    return req, pref


def required_years(text: str) -> int | None:
    best = None
    for m in YEARS_RE.finditer(text or ""):
        lo = int(m.group(1))
        if 0 < lo <= 20:
            best = lo if best is None else min(best, lo)   # most lenient stated requirement
    return best


def _title_fit(title: str, phrases: list[str]) -> float:
    t = (title or "").lower()
    best = 0.0
    for phrase in phrases:
        if phrase in t:
            return 1.0
        words = set(phrase.split())
        sc = len(words & set(re.findall(r"[a-z/]+", t))) / len(words)
        best = max(best, sc if sc >= 0.67 else 0)
    return best


def responsibilities_hit(desc: str, spec: dict) -> list[str]:
    return [r for r in spec.get("responsibilities", []) if re.search(r, desc or "", re.I)]


def classify(title: str, cfg: dict) -> list[tuple[str, str, float]]:
    """All profiles a title could belong to: (profile, 'primary'|'related', fit)."""
    out = []
    for name, spec in cfg["profiles"].items():
        f = _title_fit(title, spec["titles"])
        if f:
            out.append((name, "primary", f))
            continue
        f = _title_fit(title, spec.get("related_titles", []))
        if f:
            out.append((name, "related", f))
    return out


def family_years(profile: dict, family: str | None, cfg: dict | None = None) -> float:
    exp = profile["experience"]
    basis = ((cfg or {}).get("profiles", {}).get(family) or {}).get("years_basis") if cfg else None
    if family == "customer_support_mgmt" or basis == "customer_support":
        return float(profile.get("skills", {}).get("customer support", exp["relevant_technical_years"]))
    return float(exp["relevant_technical_years"])


def _score_for_profile(name: str, kind: str, fit: float, job: dict, profile: dict, cfg: dict) -> dict:
    spec = cfg["profiles"][name]
    title, desc = job["title"], job.get("description") or ""
    loc = (job.get("location") or "").lower()
    f = cfg["filters"]
    out = {"filter_reason": None, "missing": [], "detail": {"profile": spec.get("label", name), "match": kind},
           "family": name, "score": 0.0}
    full_desc = len(desc) >= 200

    # --- related titles must prove the work matches
    hits = responsibilities_hit(desc, spec)
    out["detail"]["responsibilities_matched"] = len(hits)
    if kind == "related":
        if not full_desc:
            out["filter_reason"] = f"related title for {spec.get('label', name)} - needs the full description to check responsibilities"
            return out
        if len(hits) < spec.get("min_responsibilities", 3):
            out["filter_reason"] = (f"related title, but only {len(hits)} of {spec.get('label', name)}'s "
                                    f"core responsibilities appear in the description")
            return out
    role_pts = 20 * fit if kind == "primary" else 14 * fit

    if name != "customer_support_mgmt" and any(w in f" {title.lower()} " for w in cfg["search"]["senior_title_words"]):
        out["filter_reason"] = "senior-level title"
        return out

    # --- location
    accept = cfg["search"]["locations"]["accept"]
    if job.get("remote") or any(k in loc for k in cfg["search"]["locations"]["remote_keywords"]):
        loc_pts = 10
    elif any(c in loc for c in accept if c not in ("india", "remote")):
        loc_pts = 10
    elif not loc or not re.sub(GENERIC_LOC, " ", loc).strip():
        loc_pts = 6
    else:
        out["filter_reason"] = f"location '{job.get('location')}' not in preferred locations"
        return out

    # --- salary
    smax = job.get("salary_max")
    if smax is None and job.get("salary_min") is None:
        smax = parse_salary_inr(desc)[1]
    if smax and smax < f["min_annual_salary_inr"]:
        out["filter_reason"] = f"stated salary max ₹{smax:,} below your ₹{f['min_annual_salary_inr']:,} minimum"
        return out
    sal_pts = 5 if smax else 3

    # --- experience
    need = required_years(desc)
    have = family_years(profile, name, cfg)
    if need is None:
        exp_pts = 12
    elif need <= have:
        exp_pts = 15
    elif need <= have + 1:
        exp_pts = 9
        out["missing"].append(f"asks for {need}+ years; you have {have:g} relevant")
    elif name != "customer_support_mgmt" and need > f["max_required_years_technical"]:
        out["filter_reason"] = f"requires {need}+ years (relevant experience: {have:g})"
        return out
    else:
        exp_pts = 4
        out["missing"].append(f"asks for {need}+ years; you have {have:g} relevant")

    # --- skills: profile priorities (35) + overall required coverage (15)
    have_sk = profile_skills(profile)
    req, pref = extract_skills(desc)
    if not full_desc:
        pri_pts, cov_pts = 20, 9
        out["missing"].append("full description not available yet - score is provisional")
    else:
        jd = req | pref
        pri = set(spec.get("priority_skills", [])) & jd
        pri_hit = pri & have_sk
        pri_pts = 35 * len(pri_hit) / len(pri) if pri else 18
        cov_pts = 15 * (len(req & have_sk) / len(req) if req else 0.6)
        missing_req = sorted(req - have_sk)
        if missing_req:
            out["missing"].append("required skills not in your profile: " + ", ".join(missing_req))
        out["detail"].update(priority_matched=sorted(pri_hit), priority_asked=sorted(pri),
                             skills_matched=sorted((req | pref) & have_sk), skills_required=sorted(req))

    if DEGREE_RE.search(desc):
        out["missing"].append("mentions a CS/engineering degree (yours: B.Sc Hotel Management)")

    total = role_pts + loc_pts + sal_pts + exp_pts + pri_pts + cov_pts
    out["detail"].update(role=round(role_pts, 1), location=loc_pts, salary=sal_pts, experience=exp_pts,
                         priority=round(pri_pts, 1), coverage=round(cov_pts, 1), required_years=need)
    out["score"] = round(total, 1)
    return out


def score_job(job: dict, profile: dict, cfg: dict) -> dict:
    """Score against every matching profile; keep the best eligible result."""
    cands = classify(job["title"], cfg)
    if not cands:
        return {"filter_reason": "title not in target roles", "missing": [], "detail": {}, "family": None, "score": 0.0}
    results = [_score_for_profile(n, k, fit, job, profile, cfg) for n, k, fit in cands]
    ok = [r for r in results if not r["filter_reason"]]
    if ok:
        best = max(ok, key=lambda r: r["score"])
        others = {r["family"]: r["score"] for r in ok if r is not best}
        if others:
            best["detail"]["also_fits"] = others
        return best
    return results[0]


def run(db: DB, profile: dict, cfg: dict, rescore: bool = False) -> dict:
    where = "status IN ('discovered','scored','filtered')" if rescore else "status='discovered'"
    rows = db.q(f"SELECT * FROM jobs WHERE {where}")
    stats = {"scored": 0, "filtered": 0}
    for r in rows:
        res = score_job(dict(r), profile, cfg)
        status = "filtered" if res["filter_reason"] else "scored"
        db.x("UPDATE jobs SET role_family=?, score=?, score_detail=?, missing=?, filter_reason=?, status=? WHERE id=?",
             (res["family"], res["score"], json.dumps(res["detail"]), json.dumps(res["missing"]),
              res["filter_reason"], status, r["id"]))
        stats[status] += 1
    db.audit("score_run", stats)
    return stats
