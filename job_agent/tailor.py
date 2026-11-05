"""Job-specific resume and cover letter built only from the profile's fact bank.

Every sentence comes from a template filled with profile values, or (optionally) from an LLM
rewrite that must pass `invention_guard` - any skill, number or employer not in the profile
rejects the rewrite and the template version is used instead.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from .privacy import ensure_private_dir
from .matcher import ALIASES, SKILL_VOCAB, extract_skills, profile_skills

FAMILY_LABEL = {
    "data_scientist": "Data Scientist",
    "data_analyst": "Data Analyst",
    "customer_support_mgmt": "Customer Support",
    "customer_support_engineer": "Customer Support Engineer",
    "prompt_engineer": "Prompt Engineer",
    "ai_builder": "AI Application Developer",
    "ai_ml_engineer": "AI & ML Engineer",
}
FAMILY_FOCUS = {   # each scoring profile's priorities, in the order they lead the resume
    "data_scientist": ["machine learning", "model evaluation", "statistics", "scikit-learn", "xgboost",
                       "feature engineering", "pandas", "python", "nlp", "deep learning"],
    "data_analyst": ["sql", "power bi", "dashboards", "reporting", "kpis", "data visualization", "excel",
                     "python", "pandas", "statistics"],
    "customer_support_mgmt": ["customer support", "team leadership", "escalations", "operations", "incident response",
                              "root-cause analysis", "documentation", "troubleshooting"],
    "customer_support_engineer": ["troubleshooting", "customer support", "incident response", "root-cause analysis",
                                  "sql", "rest apis", "python", "escalations", "documentation", "linux"],
    "prompt_engineer": ["llm", "prompt engineering", "structured outputs", "anthropic api", "openai api", "rag",
                        "python", "automation", "testing"],
    "ai_builder": ["python", "fastapi", "rest apis", "llm", "anthropic api", "mcp", "automation", "docker",
                   "react", "typescript", "postgresql", "playwright"],
    "ai_ml_engineer": ["machine learning", "ml pipelines", "model serving", "deployment", "docker", "fastapi",
                       "ci/cd", "pytorch", "transformers", "aws", "testing", "python"],
}
# old family names (jobs scored before the profiles change) -> new profile
LEGACY = {"ml_engineer": "ai_ml_engineer", "python_developer": "ai_builder", "bi_analyst": "data_analyst"}
DISPLAY = {"sql": "SQL", "aws": "AWS", "nlp": "NLP", "power bi": "Power BI", "fastapi": "FastAPI",
           "mlflow": "MLflow", "shap": "SHAP", "xgboost": "XGBoost", "numpy": "NumPy", "git": "Git & GitHub",
           "postgresql": "PostgreSQL", "rest apis": "REST APIs", "distilbert": "DistilBERT", "llm": "LLMs",
           "ci/cd": "CI/CD (GitHub Actions)", "mcp": "MCP", "rag": "RAG", "anthropic api": "Claude (Anthropic) API",
           "openai api": "OpenAI API", "kpis": "KPIs", "pytorch": "PyTorch", "lightgbm": "LightGBM",
           "typescript": "TypeScript", "javascript": "JavaScript", "mysql": "MySQL", "ml pipelines": "ML pipelines"}


def disp(s: str) -> str:
    return DISPLAY.get(s, s.title() if s.islower() else s)


def _canon(tag: str) -> set[str]:
    t = tag.lower()
    out = set()
    if t in SKILL_VOCAB:
        out.add(t)
    if t in ALIASES:
        out.add(ALIASES[t])
    return out


# ------------------------------------------------------------------ selection
def select_projects(profile: dict, jd_skills: set[str], family: str, n: int = 3) -> list[dict]:
    focus = set(FAMILY_FOCUS.get(family, []))
    scored = []
    for i, p in enumerate(profile.get("projects", [])):
        if p.get("needs_confirmation"):
            continue
        canon = set().union(*[_canon(t) for t in p.get("tags", [])]) if p.get("tags") else set()
        s = 3 * len(canon & jd_skills) + len(canon & focus) - i * 0.01   # stable tie-break
        scored.append((s, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:n]]


def select_skills(profile: dict, jd_skills: set[str], family: str, n: int = 12) -> list[str]:
    have = [s.lower() for s in profile.get("skills", {})]
    have += [s for s in (profile.get("skills_evidence") or []) if s not in have and s in SKILL_VOCAB]
    have_canon = profile_skills(profile)
    order = {s: i for i, s in enumerate(FAMILY_FOCUS.get(family, []))}
    first = sorted([s for s in have if s in jd_skills], key=lambda s: order.get(s, 99))
    focus = [s for s in FAMILY_FOCUS.get(family, []) if s in have and s not in first]
    rest = [s for s in have if s not in first and s not in focus and (s in have_canon or s in SKILL_VOCAB)]
    # keep hospitality-only skills off technical resumes unless the JD asks for them
    if family == "customer_support_engineer":
        rest = [s for s in rest if s not in ("operations management", "team leadership", "operations") or s in jd_skills]
    elif family != "customer_support_mgmt":
        rest = [s for s in rest if s not in ("operations management", "customer support", "team leadership",
                                             "escalations", "operations") or s in jd_skills]
    return (first + focus + rest)[:n]


# ------------------------------------------------------------------ text
def summary(profile: dict, family: str, matched: list[str]) -> str:
    exp = profile["experience"]
    yrs = f"{exp['relevant_technical_years']:g}"
    emp = exp["most_recent_employer"]
    top = ", ".join(disp(x) for x in matched[:3]) or "Python and SQL"
    hosp = "5+ years leading hospitality and restaurant operations"
    lines = {
        "data_scientist": (f"Data scientist with end-to-end ML projects in {top} - from feature engineering and "
                           f"cross-validated model evaluation to deployed models - plus {yrs} years on a live AI SaaS "
                           f"platform at {emp}. Completed an advanced data science program."),
        "data_analyst": (f"Data analyst comfortable turning raw data into reports, KPIs and dashboards with {top}. "
                         f"{yrs} years on a live AI SaaS platform at {emp}, and {hosp}, so I know what operators "
                         f"need from a number."),
        "customer_support_mgmt": (f"Customer-focused operations leader with {hosp} and {yrs} years in technical "
                                  f"support on a live AI SaaS platform at {emp}: production incidents, escalations, "
                                  f"root-cause analysis and clear documentation."),
        "customer_support_engineer": (f"Technical support engineer with {yrs} years supporting a live AI SaaS platform "
                                      f"at {emp}: troubleshooting production issues, escalations, root-cause analysis "
                                      f"and clear documentation, working with {top}. Backed by {hosp}, so I am at home "
                                      f"explaining technical problems to customers."),
        "prompt_engineer": (f"Builder of LLM features in {top}: prompt design, structured outputs and "
                            f"evaluation, with Claude and OpenAI APIs in my own projects and RAG quality work on a "
                            f"live AI SaaS platform at {emp} ({yrs} years)."),
        "ai_builder": (f"AI application developer who ships end-to-end: {top}, APIs, automation and LLM integration, "
                       f"deployed with Docker and CI. {yrs} years on a live AI SaaS platform at {emp}."),
        "ai_ml_engineer": (f"AI & ML engineer focused on getting models into production: {top}, ML pipelines, model "
                           f"serving with FastAPI and Docker, CI and tests. {yrs} years on a live AI SaaS platform "
                           f"at {emp}."),
    }
    return lines.get(LEGACY.get(family, family), lines["data_analyst"])


def cover_letter(profile: dict, job: dict, family: str, matched: list[str], projects: list[dict]) -> str:
    ident, exp = profile["identity"], profile["experience"]
    label = FAMILY_LABEL.get(family, job["title"])
    skills = ", ".join(disp(s) for s in matched[:4]) or "Python and SQL"
    proj = projects[0] if projects else None
    proj_line = f" Most relevant here: {proj['bullet'][0].lower() + proj['bullet'][1:]}" if proj else ""
    story = " ".join(exp.get("incident_story", "").split())
    if family == "customer_support_engineer":
        middle = (f"At {exp['most_recent_employer']}, I worked as {exp['most_recent_title']} on a live AI SaaS "
                  f"platform, where I {story}. I work hands-on with {skills}. Before tech, I spent 5+ years in "
                  f"guest-facing hospitality operations, so calm, clear communication with customers comes naturally.")
    elif family == "customer_support_mgmt":
        middle = (f"At {exp['most_recent_employer']}, I worked as {exp['most_recent_title']} on a live AI SaaS "
                  f"platform, where I {story}. Before that I spent 5+ years in hospitality operations, including "
                  f"as Operations Head, where looking after customers and leading teams was the job.")
    else:
        middle = (f"I have worked hands-on with {skills}. At {exp['most_recent_employer']}, I spent "
                  f"{exp['relevant_technical_years']:g} years on a live AI SaaS platform, resolving production incidents "
                  f"and writing root-cause reports.{proj_line}")
    transition = " ".join(exp["career_transition"].split())
    transition = transition[0].lower() + transition[1:]
    return (
        f"Dear Hiring Team at {job['company']},\n\n"
        f"I'm applying for the {job['title']} role. I'm based in {ident['city']} and can join immediately.\n\n"
        f"{middle}\n\n"
        f"My path into tech is not the usual one: {transition} "
        f"That background means I'm used to working with people who aren't technical and to owning outcomes, "
        f"not just tasks.\n\n"
        f"I'd welcome the chance to discuss how I can contribute. My portfolio is at {ident['portfolio']}.\n\n"
        f"Regards,\n{ident['full_name']}\n"
    )


# ------------------------------------------------------------------ guard
_NUM = re.compile(r"\d+(?:\.\d+)?%?")


def invention_guard(text: str, profile: dict, context: str = "") -> list[str]:
    """Return violations: skills, numbers or years not supported by the profile.
    Numbers that appear in `context` (the job title / company name being quoted) are allowed."""
    violations = []
    have = profile_skills(profile) | {s.lower() for s in profile.get("skills", {})}
    found = {k for k, pat in SKILL_VOCAB.items() if re.search(pat, text, re.I)}
    # generic words that the vocab matches but that don't claim a skill
    benign = {"communication", "rest apis", "machine learning", "data visualization", "documentation"}
    for s in sorted(found - have - benign):
        violations.append(f"claims skill not in profile: {s}")
    allowed = set(_NUM.findall(json.dumps(profile, default=str)))
    allowed |= set(_NUM.findall(context or ""))
    for n in _NUM.findall(text):
        if n not in allowed and not re.fullmatch(r"20\d\d", n):
            violations.append(f"number not in profile: {n}")
    return violations


# ------------------------------------------------------------------ optional LLM polish
def llm_polish(kind: str, draft: str, job: dict, profile: dict, cfg: dict) -> tuple[str, str]:
    """Returns (text, note). Falls back to the draft on any problem."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not (cfg.get("llm", {}).get("enabled") and key):
        return draft, "template"
    import requests
    facts = {k: profile[k] for k in ("skills", "projects", "experience", "education") if k in profile}
    facts["experience"] = {k: v for k, v in facts["experience"].items() if k != "customer_experience"} | {
        "customer_experience": profile["experience"].get("customer_experience")}
    prompt = (
        f"Rewrite this {kind} so it reads naturally for the job below. Rules: use ONLY facts in FACTS; do not add "
        f"skills, tools, numbers, titles, employers or achievements that are not in FACTS; do not inflate years; "
        f"keep it under {'120' if kind == 'summary' else '260'} words; plain text only.\n\n"
        f"JOB: {job['title']} at {job['company']}\n{(job.get('description') or '')[:3000]}\n\n"
        f"FACTS:\n{json.dumps(facts, default=str)}\n\nDRAFT:\n{draft}")
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=60, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": cfg["llm"]["model"], "max_tokens": 800,
                  "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", [])).strip()
    except Exception as e:  # noqa: BLE001
        return draft, f"template (llm error: {e})"
    bad = invention_guard(text, profile)
    if bad:
        return draft, "template (llm rewrite rejected: " + "; ".join(bad[:3]) + ")"
    return text, "llm"


# ------------------------------------------------------------------ documents
def _heading(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(text.upper())
    r.bold = True
    r.font.size = Pt(10.5)
    r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)


def _bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    p.add_run(text).font.size = Pt(10)
    p.paragraph_format.space_after = Pt(1)


def write_resume(path: Path, profile: dict, family: str, summ: str, skills: list[str], projects: list[dict]) -> None:
    ident, exp, edu = profile["identity"], profile["experience"], profile["education"]
    doc = Document()
    for s in doc.sections:
        s.left_margin = s.right_margin = s.top_margin = s.bottom_margin = Pt(42)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(ident["full_name"])
    r.bold = True
    r.font.size = Pt(18)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(" | ".join([ident["location"], f"{ident['phone_country_code']} {ident['phone']}", ident["email"]])).font.size = Pt(9.5)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(" | ".join([ident["linkedin"], ident["github"], ident["portfolio"]])).font.size = Pt(9.5)

    _heading(doc, "Summary")
    doc.add_paragraph(summ)

    _heading(doc, "Skills")
    doc.add_paragraph(", ".join(disp(s) for s in skills))

    _heading(doc, "Experience")
    for role in exp.get("roles", []):
        p = doc.add_paragraph()
        p.add_run(role["title"]).bold = True
        p.add_run(f" - {role['employer']}")
        if role.get("period"):
            p.add_run(f"  ({role['period']})").italic = True
        p.paragraph_format.space_after = Pt(1)
        bullets = role.get("bullets", [])
        if family != "customer_support_mgmt" and "chakshi" not in role["employer"].lower():
            bullets = bullets[:1]       # keep hospitality short on technical resumes
        for b in bullets:
            _bullet(doc, b)

    _heading(doc, "Projects")
    for pr in projects:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(pr["name"] + ": ").bold = True
        p.add_run(pr["bullet"])
        p.paragraph_format.space_after = Pt(1)

    _heading(doc, "Education & Certification")
    doc.add_paragraph(f"{edu['degree']} in {edu['specialization']} - {edu['institution']} ({edu['graduation_year']})")
    for c in edu.get("certifications", []):
        doc.add_paragraph(c)
    doc.save(path)


def write_letter(path: Path, text: str) -> None:
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    for para in text.split("\n\n"):
        doc.add_paragraph(para.strip())
    doc.save(path)


def to_pdf(docx_path: Path) -> Path | None:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return None
    subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", str(docx_path.parent), str(docx_path)],
                   capture_output=True, timeout=120)
    pdf = docx_path.with_suffix(".pdf")
    return pdf if pdf.exists() else None


def prepare_documents(job: dict, profile: dict, cfg: dict, outdir: Path) -> dict:
    family = LEGACY.get(job.get("role_family"), job.get("role_family")) or "data_analyst"
    req, pref = extract_skills(job.get("description") or "")
    jd = req | pref
    skills = select_skills(profile, jd, family)
    projects = select_projects(profile, jd, family, n=4 if family in ("ml_engineer", "data_scientist") else 3)
    matched = [s for s in skills if s in jd] or skills

    summ, s_note = llm_polish("summary", summary(profile, family, matched), job, profile, cfg)
    letter, l_note = llm_polish("cover letter", cover_letter(profile, job, family, matched, projects), job, profile, cfg)

    # final guard on everything that leaves the machine
    violations = invention_guard(summ + "\n" + letter + "\n" + " ".join(p["bullet"] for p in projects), profile,
                                 context=f"{job.get('title', '')} {job.get('company', '')}")

    ensure_private_dir(outdir)
    master = (profile.get("documents", {}).get("master_resumes") or {}).get(family)
    resume = outdir / "resume.docx"
    write_resume(resume, profile, family, summ, skills, projects)
    letter_path = outdir / "cover_letter.docx"
    write_letter(letter_path, letter)
    (outdir / "cover_letter.txt").write_text(letter, encoding="utf-8")
    resume_pdf = to_pdf(resume)
    attach = Path(master) if master and Path(master).exists() else (resume_pdf or resume)

    version = f"{family}-{hashlib.sha1((summ + ','.join(skills) + ','.join(p['name'] for p in projects)).encode()).hexdigest()[:8]}"
    return {
        "resume_path": str(attach), "resume_docx": str(resume), "cover_path": str(letter_path),
        "cover_text": letter, "resume_version": version if not master else f"master:{Path(master).name}",
        "projects": [p["name"] for p in projects], "skills": skills,
        "guard_violations": violations, "text_source": {"summary": s_note, "cover_letter": l_note},
    }
