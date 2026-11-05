# EMC — Error Makes Clever

> A customised, autonomous **job-search agent**. It discovers roles, scores them against your profile, tailors a resume and cover letter for each, answers application forms, and submits on official ATS platforms — **with a human approval gate and a full audit trail**. Built end-to-end: a Python agent + a Next.js / Supabase product with authentication and per-user data.

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-61%20passing-2ea44f)
![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)
![Supabase](https://img.shields.io/badge/Supabase-Auth%20%2B%20RLS-3FCF8E?logo=supabase&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-browser%20automation-2EAD33?logo=playwright)

**Status:** agent is code-complete and tested (61 automated tests). The EMC web product (accounts, email-OTP auth, per-role resumes) works end-to-end locally on Supabase. Not yet deployed to production / no public users.

---

## The problem

Manual job searching is exhausting long before you land a job — emotional fatigue, lost motivation, and anxiety from applying into the void with little response. **EMC carries the repetitive, draining part** — finding the right roles, tailoring documents, filling forms — so you keep your energy for interviews, while still approving everything that goes out.

*Error Makes Clever*: learn from the grind, then automate it.

---

## What it does

The agent runs a daily pipeline: **discover → match → tailor → answer → apply → track.**

| Stage | Module | What happens |
|---|---|---|
| **Discover** | `sources/*`, `discover.py` | Official **Greenhouse / Lever / Ashby / Workable** APIs, remote boards (**Remote OK, We Work Remotely, Himalayas**), **Remotive**, **JobsPipe** (LinkedIn/Indeed/ATS), and job-alert emails (read-only IMAP or `.eml`) + manual CSV. Dedupes (same company + similar title), tracks deadlines. |
| **Match** | `matcher.py` | Scores each job **/100** (role, skills, experience, location, salary) against **7 role profiles**; the best-fit profile wins. Filters senior / wrong-city / underpaid / over-experienced roles and lists missing requirements. |
| **Tailor** | `tailor.py` | Per-job resume (`.docx`/`.pdf`) + cover letter, built **only from your profile's fact bank**. An **invention guard** rejects any skill, number, or employer you didn't actually list. Optional LLM polish runs under the same guard. |
| **Answer** | `answers.py` | ~60+ application-question patterns, skill-year questions, dropdown/radio option-matching. **Unknown questions are flagged, never guessed. Government IDs are never auto-filled.** |
| **Apply** | `formfill.py`, `apply.py` | Playwright fills multi-step forms, uploads files, validates, detects errors & CAPTCHAs, **verifies the confirmation page**, and screenshots before/after. |
| **Track** | `db.py`, `tracker.py` | SQLite: statuses, resume versions, follow-ups (7 days), auto no-response (30 days), performance by role/source/resume, and a complete audit trail. |

### Design principles
- **Human-in-the-loop by default** — nothing auto-submits during the approval phase; after that, only above a strict quality bar (see config).
- **Never fabricates** — the invention guard keeps every resume line and form answer traceable to your real profile.
- **Respects platform terms** — LinkedIn / Naukri / Indeed and similar are **assist-only** (the agent prepares the pack; *you* click submit). Only official public APIs / standard ATS forms are auto.
- **Auditable** — every decision, document, answer, approval, and proof-of-submission is logged.
- **Local-first & private** — your profile and documents stay on your machine; only a privacy-filtered subset is ever mirrored to the cloud.

---

## Architecture

```
                          LOCAL (your machine)                         CLOUD
┌─────────────────────────────────────────────────┐      ┌───────────────────────────────┐
│  Job Agent (Python)                               │      │  Supabase                     │
│  discover → match → tailor → answer → apply       │      │   • Auth (email OTP + password)│
│  SQLite = source of truth (private/tracker.db)    │      │   • Postgres + RLS            │
│  Playwright drives real ATS forms (headful/assist)│      │   • Storage (private resumes) │
│                                                   │      │                               │
│   └─ sync-supabase ──(service key, privacy-filtered)────▶│  jobs / applications / stats  │
│   └─ seekers ◀──(reads consented users)──────────────────│  job_seekers / resumes        │
└─────────────────────────────────────────────────┘      └──────────────┬────────────────┘
                                                                         │ anon key + RLS
                                                          ┌──────────────▼────────────────┐
                                                          │  EMC Web (Next.js, web-next/)  │
                                                          │  landing · auth · dashboard    │
                                                          │  per-role resume intake        │
                                                          └────────────────────────────────┘
```

- **Agent** (local Python) is the engine and the source of truth.
- **EMC Web** (`web-next/`, Next.js 15 + Supabase) is the product: a landing page, email-based accounts, and a per-role resume intake. Each user owns their data under row-level security; files live in a private Storage bucket.
- The agent **mirrors** a privacy-filtered read-model (jobs, application status, a dashboard snapshot — never raw answers or profile) to Supabase for the showcase, and reads **consented** users to decide who it may apply for.

---

## Agent configuration

All behaviour is driven by [`config/config.yaml`](config/config.yaml) (safe to share — no personal data). Personal answers live in `private/profile.yaml`, which is **git-ignored and never committed**.

### Scoring profiles (`profiles`)
Each job is scored against every profile whose title matches; a *related* title only counts when the description shows enough of that profile's responsibilities (`min_responsibilities`). The best-fitting profile wins and sets the resume's skill order and summary.

| Profile | Targets (examples) | Experience basis |
|---|---|---|
| `data_scientist` | Data Scientist, Applied Scientist | technical |
| `data_analyst` | Data / BI / Product Analyst | technical |
| `ai_builder` | AI Application Engineer, GenAI Dev, Forward-Deployed Engineer | technical |
| `ai_ml_engineer` | ML / AI / MLOps / LLM Engineer | technical |
| `prompt_engineer` | Prompt / LLM / GenAI specialist | technical |
| `customer_support_mgmt` | Support / CX Manager, Success Ops | customer-support |
| `customer_support_engineer` | Technical / Product Support Engineer | technical |

Scoring weights (per 100): **role 25 · skills 40 (priority skills carry most) · experience 20 · location 10 · salary 5.**

### Search, filters & limits
| Key | Default | Meaning |
|---|---|---|
| `search.locations.accept` | remote, Coimbatore, Bengaluru, Chennai, India | locations kept |
| `search.senior_title_words` | senior, lead, principal, staff, … | titles treated as too senior |
| `filters.min_annual_salary_inr` | 500000 | reject only when a job **states** a max below this |
| `filters.max_required_years_technical` | 3 | tech roles asking for more are filtered out |
| `filters.min_match_score` | 55 | below this, never auto-applied (still listed) |
| `limits.daily_application_cap` | 150 | hard ceiling across all sources |
| `limits.per_company_per_30_days` | 3 | per-company throttle |
| `limits.duplicate_window_days` | 90 | same company + similar title = duplicate |
| `limits.seconds_between_submissions` | [45, 120] | randomised pacing |

### Autonomy gate (`autonomy`)
```
Phase 1 (approval):  every submission waits for you until
                     days ≥ 3  AND  ≥ 20 applications reviewed by you.
Phase 2 (auto):      auto-submit ONLY when ALL hold, else fall back to approval —
                     platform_policy = auto
                     score ≥ 70
                     no unanswered required fields
                     no answers flagged for review
                     no CAPTCHA
                     invention guard passed
```

### Platform policy (`platforms`)
| Policy | Platforms | Behaviour |
|---|---|---|
| `auto` | Greenhouse, Lever, Ashby, Workable (+ `trusted_career_domains`) | agent fills **and submits** |
| `assist` | Remote OK, WWR, Himalayas, Remotive, LinkedIn, Naukri, Indeed, Foundit, Instahyre, other | agent prepares the pack & opens the page, **you submit** (their terms prohibit bots) |

### Sources (`sources`)
Remotive API · Remote OK (JSON) · We Work Remotely (RSS) · Himalayas (JSON, India filter) · JobsPipe (credit-guarded, delta-polled) · company ATS boards (`config/companies.yaml`) · job-alert emails (opt-in IMAP) · manual CSV. India-eligibility checks drop "US-only" roles; non-INR salaries aren't compared to the ₹ minimum.

### Optional LLM polish (`llm`)
Disabled by default — tailoring then uses deterministic, fact-bank-only templates. When enabled (`provider: anthropic`, `model: claude-sonnet-5-5`), an LLM rewrite is allowed **only if it passes the same invention guard**; otherwise the template version is used.

---

## Tech stack

**Agent:** Python 3.14 · Playwright · python-docx · PyYAML · requests · cryptography · SQLite · pytest
**Web:** Next.js 15 (App Router) · React 19 · TypeScript · `@supabase/ssr`
**Platform:** Supabase (Auth, Postgres + RLS, Storage) · Brevo (SMTP for email OTP) · Vercel (target)

---

## Repository structure

```
job_agent/            # the Python agent (one module per pipeline stage)
  sources/            # ATS APIs, remote boards, JobsPipe, alert emails
  matcher.py tailor.py answers.py apply.py formfill.py tracker.py db.py
  api.py mirror.py seekers.py   # read-models, Supabase mirror, per-user matching
  web.py              # optional local FastAPI UI (localhost)
config/               # config.yaml (shareable) + companies.yaml (ATS tokens)
web-next/             # EMC web product (Next.js + Supabase)
supabase/             # schema.sql, intake.sql, resumes.sql, auth.sql (RLS)
tests/                # 61 tests (offline)
private/              # YOUR profile, documents, DB — git-ignored, never committed
```

---

## Quickstart

### 1) The agent (Windows)
```bat
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
python -m pytest -q                 :: 61 tests should pass
python -m job_agent run             :: discover -> score -> prepare -> apply (prompts for approval)
```
1. Fill `private/profile.yaml` (every resume line and answer comes from here).
2. Add ATS board tokens to `config/companies.yaml`, then `python -m job_agent check-boards`.
3. (Optional) Gmail app password in `private/.env` for alert emails.

### 2) The web product
```bash
cd web-next
cp .env.local.example .env.local     # public, browser-safe keys only
npm install
npm run dev                          # http://localhost:3000
```

### CLI reference
| Command | Does |
|---|---|
| `run` | full daily routine (discover → score → prepare → apply) |
| `jobs` / `review` | ranked jobs / items waiting on you (with reasons) |
| `apply --ids 3 5` | submit specific approved applications |
| `status 12 interview "HR call Mon"` | record an outcome |
| `report` / `audit 12` | progress & what's working / full trail for one application |
| `sync-supabase` | mirror privacy-filtered read-models to Supabase |
| `seekers` | list consented web users and whether each targeted role has a resume (**READY / BLOCKED**) |
| `seed-demo` | load synthetic showcase data |

---

## Authentication & data model (web)

- **Email accounts** via Supabase Auth — create an account (name, phone, email, password), verify the email with a code, then sign in with email + password.
- **Per-user ownership** — `job_seekers` and `resumes` rows, and Storage objects, are isolated with RLS on `auth.uid()` (verified: cross-user reads blocked, spoofed-owner inserts rejected 403).
- **Per-role resumes** — a user attaches a resume for *each* role they target; the agent applies to a role only once it has a matching resume (`job_agent seekers`).

Environment variables (never commit real values):
- Web (`web-next/.env.local`): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` *(RLS-gated, browser-safe)*
- Agent mirror (`private/.env`): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` *(secret — server-side only)*

---

## Testing

```bash
python -m pytest -q      # 61 tests, offline
```
Covers salary/deadline/alert-email parsing, dedup, scoring (good match ≥ 70; senior / wrong-city / over-experienced / low-pay filtered), answer coverage (unknowns flagged, IDs never filled), invention-guard enforcement, multi-step form filling, a dry-run end-to-end flow, and the per-user resume↔role readiness matcher.

---

## Roadmap

- [ ] Per-user agent run — take a READY web user and search/apply on their behalf
- [ ] Password reset / recovery flow
- [ ] Brevo domain authentication (DKIM/SPF) for deliverability
- [ ] Deploy to `emc.sinwansiraj.com`

---

## License

[MIT](LICENSE) © 2026 Mohammed Sinwan

## Author

**Mohammed Sinwan** — [sinwansiraj.com](https://sinwansiraj.com) · [LinkedIn](https://linkedin.com/in/mohammed-sinwan-07b410162) · [GitHub](https://github.com/Sinwansiraj)

Built as a real tool for a real job hunt, then shaped into a product.
