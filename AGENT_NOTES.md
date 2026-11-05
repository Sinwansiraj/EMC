# Job Agent — build notes and outcome

Built: 29 Oct 2026 (with Claude). Status: **code complete and tested; not yet run against live jobs.**

## What it does
| Stage | Module | Summary |
|---|---|---|
| Discover | `sources/ats.py`, `sources/feeds.py`, `discover.py` | Official Greenhouse / Lever / Ashby / Workable APIs, Remotive API, LinkedIn / Naukri / Indeed alert emails (read-only IMAP or `.eml` files), manual CSV. Stores original URL + deadline, detects new postings, merges duplicates (same company + similar title). |
| Match | `matcher.py` | Score /100: role 25, skills 40, experience 20, location 10, salary 5. Filters senior titles, other cities, stated pay below ₹5 LPA, tech roles asking > 3 yrs. Lists missing requirements. |
| Tailor | `tailor.py` | Resume (.docx/.pdf) + cover letter per job, built only from `private/profile.yaml`. Invention guard rejects any skill, number or employer not in the profile. Optional Claude polish, same guard. |
| Answer | `answers.py` | ~60 question patterns from your answer sheet; skill-year questions; option matching for dropdowns/radios. Unknown questions are never guessed. |
| Apply | `formfill.py`, `apply.py` | Playwright fills multi-step forms, uploads files, validates, detects errors and CAPTCHAs, verifies confirmation, screenshots before/after. |
| Track | `db.py`, `tracker.py` | SQLite: statuses, dates, resume versions, follow-ups (7 days), auto no-response (30 days), duplicate detection, performance by job type/source/resume version, full audit trail. |

## Settings chosen
- Roles: Data Analyst, Data Scientist, Junior ML / AI-ML Engineer (incl. FDE), Python Developer, BI Analyst, Customer Support Management
- Locations: Remote, Coimbatore, Bengaluru, Chennai
- Min salary ₹5 LPA; expected CTC ₹5.5 LPA (monthly answered as ₹45,833 gross); current CTC ₹4.5 LPA
- Daily cap 150 (as requested — recommended 20–30); max 3 per company per 30 days; 90-day duplicate window
- Autonomy: approval required for first 3 days AND first 20 reviewed applications; then auto-submit only if score ≥ 70, all required fields answered, nothing flagged, no CAPTCHA, invention guard passed
- Platforms: Greenhouse/Lever/Ashby/Workable = auto; LinkedIn/Naukri/Indeed/Foundit/Instahyre = assist (their terms ban bots — agent prepares the pack, you submit)
- Experience: 9 years total, 1.2 years relevant technical; support roles use 5 years customer-facing

## Test results (29/29 passing)
- Parsing: salary ranges (LPA, monthly), deadlines, LinkedIn/Naukri alert emails
- Dedup: same role from two sources merged; re-discovery doesn't re-queue
- Scoring: good match ≥ 70; senior / wrong city / 5+ yrs / low pay / off-target titles filtered
- Answers: 16 sample questions answered correctly, including Kubernetes → "No" flagged for review, "Why Acme?" → left for you
- Tailoring: resume + cover letter with zero invention-guard violations; guard catches fake skills and numbers
- Browser: two-step form filled (name, files, notice period, sponsorship, Python years, CTC, gender declined, privacy consent checked, newsletter left unchecked); unknown question blocked; clean form submitted and confirmation verified
- End-to-end dry run: 4 jobs → 2 ranked, 2 filtered with reasons → approval phase held submission → approved → submitted and verified; LinkedIn job routed to manual pack

## Open items before first real run
1. `private/profile.yaml` — confirm Chakshi job title against offer letter (you gave "Technical Support Engineer"; elsewhere "AI / Software Engineer")
2. Certification worded as "Advanced Data Science certification program (IIT Madras / GUVI)" — not a Master's degree
3. Add years for KSD Restaurants and Black Thunder Resort roles
4. Add company board tokens to `config/companies.yaml`, run `check-boards`
5. Optional: Gmail app password in `private/.env` for alert emails
6. Optional: map your existing resumes (Desktop\Resume_Rewrite_Output) in `profile.yaml → documents.master_resumes`
7. Consider lowering `daily_application_cap`

## Setup reminder
```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
python -m pytest -q
python -m job_agent run
```

## Update 29 Oct 2026 (evening)
**Answer coverage.** Tested against 99 common portal questions. Fixed these wrong answers:
- "years with Java/Tableau/Excel" answered 9 (now 0, flagged for you)
- 10th/12th % answered with the graduation figure (now blank until filled)
- alternate phone repeated the main number (now blank)
- GitHub URL answered "Yes" (now the URL)
- "preferred name/location" were read as referral questions (now correct)

Added slots in `private/profile.yaml` (`personal`, `open_answers`) for questions only you can answer. Government IDs are never filled automatically.

**Skills audit.** Read-only audit of GitHub (11 repos) and the Career-Audit folder, written up in `My_skills.md`.
- Projects in `profile.yaml` now use verified facts.
- Unverified items (MLflow, SHAP, Customer Health engine, Price Comparison Agent, Sara, LinkedIn MCP) are marked `needs_confirmation` and stay off resumes until you confirm them.
- Audited skills go in `skills_evidence`. They count for matching and answer "Have you used X?" with Yes; years questions on them are flagged for review.

**Six scoring profiles.** Data Scientist, Data Analyst, Customer Support Management, Prompt Engineer, AI Builder, AI & ML Engineer, set in `config.yaml → profiles`.
- Each profile has its own priority skills, which carry 35 of the 100 points, and its own resume summary and skill order.
- Related titles (BI Analyst, AI Application Engineer, LLM Engineer, Customer Success Ops Manager, ML Developer, Python Developer…) count only when the description shows enough of that profile's core responsibilities.
- A job matching several profiles is scored against each, and the best one wins.
- 43 tests pass.

## Outcome log
Record real-world results here (or run `python -m job_agent report`).

| Date | Applied | Interviews | Notes |
|---|---|---|---|
| | | | |

## Update 4 Nov 2026 — remote-board sources
New module `job_agent/sources/remote_boards.py`, wired into `discover.py`; settings under
`sources.remote_boards` in `config/config.yaml`.
- **Remote OK** — public JSON API, newest feed + one call per tag.
- **We Work Remotely** — public RSS (all-jobs feed + chosen categories).
- **Himalayas** — public JSON search API with `country=India`, one search per query, 2 pages each.
  Optional free key `HIMALAYAS_API_KEY` in `private/.env` for higher limits. Data refreshes daily.
- Only jobs open to India are kept: region/country/timezone (UTC+5:30) checks, plus a filter for
  "US only" / "must reside in the US"-style wording. Non-INR salaries are not compared to your ₹ minimum.
- All three are `assist` platforms: the agent prepares the pack, you apply. Himalayas' terms require
  applying through its `applicationLink`, which is what's stored.
- Tests: `tests/test_remote_boards.py` (5, offline). Not yet run against the live feeds — the build
  sandbox has no internet. First real check: `python -m job_agent run` and look at the discover stats/errors.

## Update 4 Nov 2026 — JobsPipe source
`job_agent/sources/jobspipe.py`, settings in `sources.jobspipe`. Key in `private/.env` (`JOBSPIPE_API_KEY`).
- Covers LinkedIn, Indeed and ATS career sites through JobsPipe's official API. LinkedIn/Indeed jobs
  stay `assist`; Greenhouse/Lever/etc. links follow their normal platform policy.
- Free plan = 1,000 credits once (1 per job returned; repeats in the same month free). Guards:
  two narrow searches (India + Coimbatore/Bengaluru/Chennai; India + remote), target titles only,
  senior titles excluded, ghost score ≤ 60, max 60 credits per run, stops below 50 remaining.
- Delta polling: once a search has been read to the end, its cursor is saved (tracker.db meta) and
  later runs fetch only new postings. Changing that search's filters starts it over.
- `discover` stats now include `jobspipe: {credits_charged, credits_remaining, pages}`.
- Remote OK fix: its `?tags=` filter is ignored by the API, so it is now one request per run.
- Tests: `tests/test_jobspipe.py` (5, offline, mocked HTTP).

## Update 4 Nov 2026 — Customer Support Engineer batch
- New scoring profile `customer_support_engineer` (config.yaml) + matching resume/cover-letter wording
  in tailor.py. Generic "support engineer" titles need 3 customer-facing responsibilities in the JD.
- Invention guard now allows numbers quoted from the job title/company (e.g. "L4", "IRC300789").
- Imported 103 JobsPipe postings (IN; Coimbatore/Bengaluru/Chennai + remote; entry/mid or unlabelled;
  last 7 days) from `private/imports/jobspipe_support_2026-11-04.json` → 96 unique, 66 matched,
  66 packs prepared in `private/applications/<job id>/`. 101 credits used, 814 left.
- Backup of the pre-import DB: `private/tracker.backup-2026-11-04.db`.
- SQLite cannot write to this folder from the Cowork VM (disk I/O error), so the import ran on a
  local copy and was copied back. `private/_to_delete/` holds a stale journal + tailor.py backup.
