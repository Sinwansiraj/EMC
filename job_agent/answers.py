"""Map application-form questions to your stated answers.

Each answer carries a confidence:
  exact   - a known question with a value you gave
  derived - computed from your values (e.g. monthly gross from annual CTC)
  review  - the agent has a best guess but a human should look (blocks auto-submit)
  unknown - no answer; never guessed (blocks submit until you fill it)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class Answer:
    value: str
    confidence: str          # exact | derived | review | unknown
    key: str = ""
    note: str = ""


def _y(v) -> str:
    return str(v)


def _lpa(n: int) -> str:
    return f"{n / 100000:g} LPA"


def build_rules(p: dict) -> list[tuple[str, str, callable]]:
    """(key, regex over the lower-cased question, value function). Order matters: first match wins."""
    i, pr, ed, ex, c, d = (p["identity"], p["preferences"], p["education"], p["experience"],
                           p["compensation"], p["declarations"])
    pe = p.get("personal") or {}
    oa = p.get("open_answers") or {}

    def want(src: dict, key: str):
        """Value from the profile, or None (-> unknown) when you haven't filled it in yet."""
        return lambda: (src.get(key) if src.get(key) not in (None, "", []) else None)

    monthly = round(c["expected_ctc_annual"] / 12)
    cur_monthly = round(c["current_ctc_annual"] / 12)
    return [
        # ---- never filled automatically
        ("gov_id", r"\bpan\b|aadha+r|passport (number|no)|bank account|ifsc|\buan\b|voter id|driving licen[cs]e (number|no)",
         lambda: None),
        # ---- personal details you fill in profile.yaml -> personal
        ("middle_name", r"middle name", want(pe, "middle_name")),
        ("dob", r"date of birth|\bdob\b|birth ?date", want(pe, "date_of_birth")),
        ("nationality", r"nationality|citizenship", want(pe, "nationality")),
        ("marital", r"marital", want(pe, "marital_status")),
        ("gender_personal", r"^\W*gender\W*$|^\W*sex\W*$", want(pe, "gender")),
        ("disability", r"disab|differently.abled|\bpwd\b", want(pe, "disability")),
        ("veteran", r"veteran|armed forces|ex-servicem", want(pe, "veteran")),
        ("spoken_languages", r"languages? (can |do )?you (speak|know)|languages known|spoken languages", want(pe, "languages")),
        ("english", r"english", want(pe, "english_proficiency")),
        ("laptop", r"laptop|own (computer|system)", want(pe, "has_laptop")),
        ("internet", r"internet|broadband|wi-?fi", want(pe, "has_internet")),
        ("vehicle", r"two.wheeler|bike|vehicle|driving licen", want(pe, "two_wheeler_and_licence")),
        ("internship", r"internship", want(pe, "open_to_internship")),
        ("pending_offers", r"(pending|other|existing) offers?|offers? in hand|holding (any|an) offer", want(pe, "pending_offers")),
        ("referral", r"\breferr|\breferral", want(pe, "referred_by")),
        ("how_heard", r"how did you (hear|find|learn|come to know)|source of (application|this job)", want(pe, "how_heard")),
        ("social", r"twitter|\bx profile|instagram|facebook", want(pe, "twitter")),
        ("pincode", r"pin ?code|postal code|zip", want(i, "pincode")),
        ("alt_phone", r"alternate|alternative|secondary (phone|mobile|number|contact)", want(pe, "alternate_phone")),
        ("permanent_address", r"permanent address", want(pe, "permanent_address")),
        ("current_address", r"(current|present|residential|postal) address|^\W*address\W*$", want(pe, "current_address")),
        # ---- open-ended answers you write once in profile.yaml -> open_answers
        ("why_join", r"why (do you want to|would you like to|are you interested in|do you wish to) (join|work)|why (us|this company|our company)\b|why join",
         want(oa, "why_join")),
        ("why_hire", r"why should we (hire|select|choose)", want(oa, "why_hire")),
        ("about_me", r"tell (us|me) about yourself|introduce yourself|describe yourself", want(oa, "about_me")),
        ("strengths", r"strengths?\b", want(oa, "strengths")),
        ("weaknesses", r"weakness", want(oa, "weaknesses")),
        ("five_years", r"(5|five) years", want(oa, "five_years")),
        ("proud_project", r"project you('re| are) (most )?proud|describe a (project|challenge)|most (challenging|significant) project",
         want(oa, "proud_project")),
        ("lwd", r"last working (day|date)|\blwd\b|serving notice", lambda: "Not applicable - not serving notice; can join immediately"),
        # ---- identity
        ("preferred_name", r"preferred (first )?name|what should we call you|nickname", lambda: i["preferred_name"]),
        ("first_name", r"^\W*first name|given name", lambda: i["first_name"]),
        ("last_name", r"^\W*(last name|surname|family name)", lambda: i["last_name"]),
        ("full_name", r"full name|^\W*name\W*$|your name|legal name", lambda: i["full_name"]),
        ("email", r"e-?mail", lambda: i["email"]),
        ("country_code", r"country code|dialing code", lambda: i["phone_country_code"]),
        ("phone", r"phone|mobile|contact number|whatsapp", lambda: i["phone"]),
        ("linkedin", r"linked\s?in", lambda: i["linkedin"]),
        ("github", r"github", lambda: i["github"]),
        ("state", r"^\W*state\W*$|state of residence|^\W*state ?/ ?province", lambda: i["state"]),
        ("portfolio", r"portfolio|personal (web)?site|website|blog", lambda: i["portfolio"]),
        ("city", r"^\W*city\W*$|current city", lambda: i["city"]),
        ("country", r"^\W*country\W*$|country of residence", lambda: i["country"]),
        ("location", r"current(ly)? location|where are you (currently )?(located|based)|^\W*location\W*$",
         lambda: i["location"]),
        # ---- work authorization & declarations (before generic yes/no rules)
        ("authorized_india", r"(legally )?(authori[sz]ed|eligible|right) to work", lambda: d["authorized_to_work_india"]),
        ("sponsorship", r"sponsor", lambda: d["needs_visa_sponsorship"]),
        ("passport", r"passport", lambda: d["valid_passport"]),
        ("background_check", r"background (check|verification)", lambda: d["background_check"]),
        ("contact_previous_employer", r"contact (your )?(previous|former|past) employer|reference check",
         lambda: d["contact_previous_employer"]),
        ("previously_applied", r"(previously|before|ever) (applied|worked|been employed)|applied (to|with|for|at) (us|this|our|the)|applied .*before",
         lambda: d["previously_applied"]),
        ("relative", r"related to (anyone |someone |any |an? )?(current )?(employee|staff|anyone)|\brelatives?\b|family members?.*(employ|work)|know anyone (who works|at)", lambda: d["relative_at_company"]),
        ("conflict", r"conflicts? of interest", lambda: d["conflict_of_interest"]),
        ("accurate", r"(confirm|certify|declare).*(accurate|true|correct)|information.*(accurate|true)",
         lambda: d["info_accurate"]),
        # ---- salary
        ("expected_monthly", r"expected.*(monthly|per month|/ ?month)|monthly.*expect",
         lambda: f"{monthly}"),
        ("current_monthly", r"current.*(monthly|per month)", lambda: f"{cur_monthly}"),
        ("expected_ctc", r"expected (ctc|salary|compensation|pay|package)|salary expectation|desired (salary|pay)",
         lambda: str(c["expected_ctc_annual"])),
        ("current_ctc", r"current (ctc|salary|compensation|package)|(present|last|previous|most recent) (ctc|salary|drawn)",
         lambda: str(c["current_ctc_annual"])),
        ("negotiable", r"negotiable", lambda: c["negotiable"]),
        # ---- availability
        ("notice_period", r"notice period", lambda: _y(ex["notice_period_days"])),
        ("join", r"when can you (join|start)|earliest (start|joining)|joining date|start date|availability to (join|start)",
         lambda: ex["join"]),
        ("relocate", r"relocat", lambda: pr["willing_to_relocate"]),
        ("night_shift", r"night shift|rotational shift|us shift|shifts?", lambda: pr["night_shifts"]),
        ("wfo", r"work from (the )?office|on-?site|in-?office|hybrid", lambda: pr["work_from_office"]),
        ("contract", r"contract (role|employment|position|basis)|open to contract", lambda: pr["open_to_contract"]),
        ("preferred_location", r"preferred (work )?location", lambda: ", ".join(pr["preferred_work_locations"])),
        # ---- education
        ("highest_qualification", r"highest (level of )?(education|qualification|degree)", lambda: ed["highest_qualification"]),
        ("degree", r"^\W*degree|what degree|degree (completed|obtained)", lambda: ed["degree"]),
        ("specialization", r"speciali[sz]ation|major|field of study|discipline", lambda: ed["specialization"]),
        ("tenth", r"\b(10th|class 10|class x\b|sslc|secondary school)", want(ed, "tenth_percentage")),
        ("twelfth", r"\b(12th|class 12|class xii\b|hsc|higher secondary|puc|intermediate)", want(ed, "twelfth_percentage")),
        ("cgpa", r"cgpa|gpa|percentage|aggregate|marks", lambda: ed["percentage"]),
        ("institution", r"college|university|institut|school", lambda: ed["institution"]),
        ("graduation_year", r"(graduation|passing|passed out|completion) year|year of (graduation|passing)",
         lambda: _y(ed["graduation_year"])),
        ("certifications", r"certification", lambda: "; ".join(ed["certifications"])),
        ("training", r"professional training", lambda: ed["professional_training"]),
        ("pursuing", r"currently pursuing|pursuing any", lambda: ed["pursuing_additional_qualification"]),
        # ---- experience
        ("relevant_years", r"relevant (work )?experience|years of experience (in|as|with) (data|ml|machine|python|analytics|ai|software)",
         lambda: _y(ex["relevant_technical_years"])),
        ("total_years", r"total (work |years of )?experience|overall experience|how many years of (total |overall |work |professional )?experience( do you have)?\W*$|years of experience\W*$",
         lambda: _y(ex["total_years"])),
        ("current_title", r"(current|most recent|latest|last) (job )?(title|designation|role|position)",
         lambda: ex["most_recent_title"]),
        ("current_employer", r"(current|previous|most recent|last|present) (employer|company|organi[sz]ation)",
         lambda: ex["most_recent_employer"]),
        ("employment_status", r"(current )?employment status|currently employed", lambda: ex["employment_status"]),
        ("reason_leaving", r"reason for (leaving|(job |a )?change|switch)|why (did|are) you (leave|leaving|looking|changing|switching)",
         lambda: ex["reason_for_leaving"]),
        ("gap", r"(employment|career) gap|gap in", lambda: f"Yes, {ex['gap_years']} year - {ex['gap_reason']}"),
        ("transition", r"career (transition|change)|why (data|tech|ai|ml|this field)", lambda: ex["career_transition"]),
        ("team", r"worked in a team|team (experience|player)", lambda: ex["worked_in_team"]),
        ("independent", r"(managed|led) projects? independently|work independently", lambda: ex["managed_projects_independently"]),
        ("customer_exp", r"(experience|worked) (with|handling) (clients|customers)|customer.facing", lambda: ex["customer_experience"]),
        # ---- technical
        ("languages", r"programming languages", lambda: "Python, SQL"),
        ("python_proficiency", r"(proficien|level).*python|python.*(proficien|level)", lambda: p["python_proficiency"]),
        ("strongest_skill", r"strongest (technical )?skill", lambda: p["strongest_skill"]),
        ("algorithms", r"(which|what) (machine learning )?algorithms", lambda: ", ".join(p["ml_algorithms"])),
    ]


# Skill names accepted in "years of experience with X" / "have you used X" questions.
YES_NO_TECH = {
    "pandas": "pandas", "numpy": "numpy", "power bi": "power bi", "scikit": "scikit-learn", "sklearn": "scikit-learn",
    "fastapi": "fastapi", "streamlit": "streamlit", "git": "git", "github": "github", "aws": "aws",
    "machine learning": "machine learning", "sql": "sql", "python": "python", "xgboost": "xgboost",
    "postgres": "postgresql", "mlflow": "mlflow", "playwright": "playwright", "nlp": "nlp", "api": "rest apis",
    "customer support": "customer support", "customer service": "customer support", "tableau": "tableau",
    "excel": "excel", "java": "java", "docker": "docker", "llm": "llm", "generative ai": "llm", "genai": "llm",
    "statistics": "statistics", "deep learning": "deep learning",
    "react": "react", "typescript": "typescript", "flask": "flask", "pytorch": "pytorch", "transformers": "transformers",
    "hugging face": "transformers", "selenium": "selenium", "mysql": "mysql", "redis": "redis", "lightgbm": "lightgbm",
    "prompt engineering": "prompt engineering", "prompt": "prompt engineering", "rag": "rag", "openai": "openai api",
    "anthropic": "anthropic api", "claude": "anthropic api", "ci/cd": "ci/cd", "github actions": "ci/cd", "mcp": "mcp",
    "mlflow": "mlflow", "shap": "shap",
}


class Answerer:
    def __init__(self, profile: dict):
        self.p = profile
        self.rules = [(k, re.compile(rx, re.I), fn) for k, rx, fn in build_rules(profile)]
        self.skills = {k.lower(): v for k, v in profile.get("skills", {}).items()}
        self.evidence = {k.lower() for k in (profile.get("skills_evidence") or [])}
        self.not_have = {k.lower() for k in (profile.get("skills_not_have") or [])}

    def _skill_question(self, q: str) -> Answer | None:
        ql = q.lower()
        years_q = re.search(r"\byears?\b|how much experience|how long", ql)
        yes_q = re.search(r"^(have|do) you (used|worked|built|deployed|have|know)|are you (familiar|proficient)", ql)
        hits = [canon for word, canon in YES_NO_TECH.items() if re.search(rf"\b{re.escape(word)}", ql)]
        if not hits and years_q:
            m = re.search(r"experience (?:do you have )?(?:with|in|using|on)\s+([A-Za-z0-9+#./ -]{2,40}?)\W*$", q, re.I)
            if m:
                tool = m.group(1).strip().lower()
                if tool in self.not_have:
                    return Answer("0", "exact", f"skill:{tool}", "you said you don't use this")
                if tool in self.skills:
                    return Answer(f"{self.skills[tool]:g}", "exact", f"skill:{tool}")
                if tool in self.evidence:
                    return Answer("1", "review", f"skill:{tool}",
                                  f"{tool}: used in your projects but years not recorded - confirm")
                return Answer("0", "review", "skill_unlisted",
                              f"'{tool}' is not in your skills list - confirm, or add it with years")
        if not hits:
            # an unknown tool/skill: answer honestly only if it's clearly a yes/no about a named tool
            m = re.search(r"(?:experience (?:with|in)|used|worked with|knowledge of)\s+([A-Za-z0-9+#. ]{2,30})\??$", q, re.I)
            if m and (years_q or yes_q):
                tool = m.group(1).strip().lower()
                if tool not in self.skills:
                    return Answer("0" if years_q else "No", "review", "skill_unlisted",
                                  f"'{tool}' is not in your skills list - confirm before sending")
            return None
        canon = hits[0]
        if canon in self.not_have:
            return Answer("0" if years_q and not yes_q else "No", "exact", f"skill:{canon}", "you said you don't use this")
        yrs = self.skills.get(canon)
        if yrs is None and canon in self.evidence:
            if years_q and not yes_q:
                return Answer("1", "review", f"skill:{canon}",
                              f"{canon}: used in your projects (My_skills.md) but years not recorded - confirm")
            return Answer("Yes", "exact", f"skill:{canon}", "evidence in My_skills.md")
        if yrs is None:
            return Answer("0" if years_q else "No", "review", f"skill:{canon}", f"{canon} not in skills list")
        if years_q and not yes_q:
            return Answer(f"{yrs:g}" if isinstance(yrs, (int, float)) else str(yrs), "exact", f"skill:{canon}")
        return Answer("Yes", "exact", f"skill:{canon}")

    def answer(self, question: str, company_previously_applied: bool | None = None) -> Answer:
        q = re.sub(r"\s+", " ", (question or "")).strip().rstrip("*").strip()
        if not q:
            return Answer("", "unknown", note="empty label")
        ql = q.lower()
        if re.search(r"years? of experience (do you have )?(with|in|using|on) |experience (do you have )?(with|in|using) ", ql) \
                and not re.search(r"relevant|total|overall|url|link", ql):
            sk = self._skill_question(q)
            if sk:
                return sk
        if (any(re.search(rf"\b{re.escape(w)}", ql) for w in YES_NO_TECH)
                and not re.search(r"proficien|level|algorithm|programming languages|strongest|url|link|profile|username|handle", ql)):
            sk = self._skill_question(q)
            if sk:
                return sk
        for key, rx, fn in self.rules:
            if rx.search(q):
                raw = fn()
                if raw is None:
                    note = ("government ID / bank detail - never filled automatically" if key == "gov_id"
                            else f"not in your profile yet ({key}) - add it to private/profile.yaml")
                    return Answer("", "unknown", key, note)
                val = ", ".join(raw) if isinstance(raw, list) else str(raw)
                conf = "exact"
                note = ""
                if key in ("expected_monthly", "current_monthly"):
                    conf, note = "derived", "gross per month = annual CTC / 12 (not take-home)"
                if key == "previously_applied" and company_previously_applied:
                    val, note = "Yes", "tracker has an earlier application to this company"
                if key == "why_join":
                    conf, note = "review", "generic answer - check it fits this company"
                if key in ("transition", "customer_exp") and len(q) > 140:
                    conf, note = "review", "long-form question - check the wording fits"
                return Answer(val, conf, key, note)
        sk = self._skill_question(q)
        if sk:
            return sk
        return Answer("", "unknown", note="no stored answer - needs you")


# ---------------------------------------------------------------- choosing an option
def _num(s: str) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", s.replace(",", ""))
    return float(m.group()) if m else None


def choose_option(answer: str, options: list[str]) -> str | None:
    """Pick the select/radio option that matches a stored answer, or None if unsure."""
    opts = [o for o in options if o and not re.match(r"(?i)^\s*(select|choose|--|please select)", o)]
    if not opts:
        return None
    a = answer.strip().lower()
    for o in opts:
        if o.strip().lower() == a:
            return o
    if a in ("yes", "no"):
        for o in opts:
            if re.match(rf"(?i)^\s*{a}\b", o.strip()):
                return o
        return None
    # numeric answer into a range option like "1-2 years", "0 - 15 days", "5+"
    n = _num(a)
    if n is not None:
        for o in opts:
            ol = o.lower().replace("–", "-")
            rng = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)", ol)
            if rng and float(rng.group(1)) <= n <= float(rng.group(2)):
                return o
            plus = re.search(r"(\d+(?:\.\d+)?)\s*\+|more than (\d+)|above (\d+)", ol)
            if plus:
                lo = float(next(g for g in plus.groups() if g))
                if n >= lo:
                    return o
            less = re.search(r"less than (\d+(?:\.\d+)?)|under (\d+)|below (\d+)", ol)
            if less and n < float(next(g for g in less.groups() if g)):
                return o
            if (n == 0 and re.search(r"immediate|fresher|no experience|none", ol)):
                return o
            single = _num(ol)
            if single is not None and single == n and not rng:
                return o
    if a.startswith("immediate"):
        for o in opts:
            if re.search(r"immediate|0 days|right away|asap", o, re.I):
                return o
    best, best_r = None, 0.0
    for o in opts:
        r = SequenceMatcher(None, a, o.lower()).ratio()
        if r > best_r:
            best, best_r = o, r
    return best if best_r >= 0.8 else None
