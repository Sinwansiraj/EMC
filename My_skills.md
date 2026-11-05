# My Skills — evidence-based inventory

Read-only audit, 29 Oct 2026. Sources:
- **GitHub** — all 11 public repos of github.com/Sinwansiraj: imports in code and notebooks, requirements.txt, package.json, CI/Docker/deploy files, READMEs.
- **Career-Audit folder** — `Career-Asset-Audit-Report.md`, `Resume-and-Interview-Pack.md`, `work-history-chapters/15-my-contribution.md` and related chapters.

Nothing was changed in either place.

## How to read the levels

| Level | Meaning | How the agent uses it |
|---|---|---|
| **A — In my public code** | Imported or configured in a GitHub repo I own | Can be on any resume. "Have you used X?" answers **Yes** |
| **B — In my local projects** | Verified authored in Career-Audit (personal projects not on GitHub) | Same as A |
| **C — Used at Chakshi** | Team production work. My hands-on share is per the Career-Audit caveats | Listed for relevant roles. "Have you used X?" answers **Yes** |
| **D — Stated by me, not found in code** | Mentioned in a README or profile, or told to the agent, but no code artifact found | Kept, but flagged in `review` until I confirm |

Years: I have **1.2 years** of relevant technical experience in total, so no single tool gets more than that. The agent answers "years with X?" from the `skills:` list in `private/profile.yaml`. For tools found only by this audit, it proposes **1** and asks me to confirm.

---

## Languages
| Skill | Level | Evidence |
|---|---|---|
| Python | A | 62 .py files + 8 notebooks across 9 repos |
| SQL | A | `schema.sql` + queries (news classifier, diabetes predictor, Redbus) |
| JavaScript | A | sinwansiraj.dev, Hotel_problems |
| TypeScript | A | Hotel_problems (React/TS) |
| Node.js / Express | B | Chakshi Developer Dashboard (Express API, 47 node:test tests) |

## Data analysis & visualization
| Skill | Level | Evidence |
|---|---|---|
| pandas, NumPy | A | 6–7 repos |
| Matplotlib, Seaborn | A | diabetes predictor, Power-prediction, lead scoring |
| Plotly | D | listed in GitHub profile README only |
| Jupyter | A | 8 notebooks |
| EDA, feature engineering | A | Power-prediction, lead scoring (`preprocessor.py`, `features`) |
| ~~Power BI~~ | Removed | Removed at your request (29 Oct). The agent answers No and never lists it |
| ~~Excel~~ | Removed | Removed at your request (29 Oct). The agent answers No and never lists it |
| Recharts (React charts) | A | Hotel_problems |

## Machine learning
| Skill | Level | Evidence |
|---|---|---|
| scikit-learn | A | diabetes predictor, Power-prediction, Swiggy, lead scoring |
| XGBoost | A | lead scoring, Power-prediction |
| LightGBM | A | Power-prediction |
| Random Forest, Logistic Regression | A | diabetes predictor, lead scoring, Power-prediction |
| K-Means, cosine-similarity recommender | A | Swiggy recommendation |
| Hyperparameter tuning (GridSearchCV) | A | diabetes predictor, Power-prediction |
| Cross-validation, ROC-AUC / precision / recall / F1, imbalanced data | A | lead scoring (5-fold CV, AUC quality gate) and diabetes predictor |
| Model persistence (joblib) | A | 3 repos |
| Data drift checks | A | lead scoring, diabetes predictor |
| Time-series regression | A | Power-prediction (household energy forecasting) |
| ~~MLflow~~ | Removed | Removed at your request (29 Oct) |
| ~~SHAP~~ | Removed | Removed at your request (29 Oct) |

## Deep learning & NLP
| Skill | Level | Evidence |
|---|---|---|
| PyTorch | A | news classifier |
| Hugging Face Transformers, Datasets, Evaluate, Accelerate | A | news classifier (DistilBERT fine-tune on AG News, 94.62% accuracy) |
| NLP text classification | A | news classifier |

## LLMs & AI applications
| Skill | Level | Evidence |
|---|---|---|
| Anthropic / Claude API | A, B | mini_zia; LinkedIn MCP server (lead scoring, outreach, sentiment) |
| OpenAI API | A | chatbot, mini_zia |
| Prompt design for structured output / rephrasing | A | mini_zia (`llm_rephraser`, optional LLM layer over deterministic insights) |
| MCP (Model Context Protocol) server | B | LinkedIn MCP server, 15 tools |
| Multi-agent orchestration, Claude Code plugins/skills/hooks | B, C | skill fleet, owner-guard (Career-Audit flags co-authorship to confirm) |
| AI agent guardrails / permission layer | B | owner-guard (owner-confirmation gates, audit trail) |
| RAG — retrieval quality, citations, evaluation | C | Chakshi #61 retrieval gate, #315 RAG discovery/eval, #303 ingestion |
| pgvector, embeddings | C | Chakshi RAG stack |
| Local LLM evaluation (Qwen) | C | Chakshi RAG generation research |

## Backend, APIs & automation
| Skill | Level | Evidence |
|---|---|---|
| FastAPI, Uvicorn, Pydantic | A | lead scoring (Render-hosted API, health endpoint) |
| Flask, Gunicorn, Jinja2 | A | diabetes predictor (login, PDF reports) |
| Streamlit | A | 5 repos |
| REST API design | A, B | lead scoring, MCP server |
| SQLAlchemy, Alembic migrations | B | LinkedIn MCP server (also in Redbus requirements) |
| Redis (caching, rate-limiting) | B | LinkedIn MCP server |
| Selenium | A | Redbus scraping pipeline |
| Playwright | B | MCP server (async collection), smoke-test runner with manual sign-in |
| Git automation | B | read-only `git log/status/merge-tree` dashboard |

## Databases
| Skill | Level | Evidence |
|---|---|---|
| PostgreSQL (psycopg2) | A | news classifier → AWS RDS |
| MySQL | A | Redbus pipeline |
| SQLite | A | diabetes predictor |
| Supabase, Row-Level Security | C | Chakshi (RLS outage fix #280, cross-tenant leak fix) |

## Cloud, DevOps & quality
| Skill | Level | Evidence |
|---|---|---|
| AWS S3, RDS (boto3) | A | news classifier |
| AWS EC2 | A | news classifier README + `deploy.sh` |
| Docker, docker-compose | A, B | lead scoring (multi-stage, non-root), MCP server |
| GitHub Actions CI | A | lead scoring + mini_zia `ci.yml` (lint, types, tests, keep-warm) |
| Render, Vercel deployment | A | lead scoring (API on Render, dashboard on Vercel), diabetes predictor |
| pytest, pytest-cov | A | lead scoring (67 tests), mini_zia, news classifier |
| Ruff, mypy | A | lead scoring CI |
| Security scanning (semgrep, trivy), Dependabot, CVE patching | C | Chakshi |
| Production CI image builds, release gates | C | Chakshi #427/#428, #361–#372 |
| Observability design | C | Chakshi Phases 1–16, M0–M4c |

## Front-end
| Skill | Level | Evidence |
|---|---|---|
| React, Vite | A | sinwansiraj.dev, Hotel_problems, lead-scoring dashboard |
| Tailwind CSS, Framer Motion, Radix UI | A | Hotel_problems, portfolio |
| TanStack Query/Table, Zustand, React Router | A | Hotel_problems |

## Operations & support (non-code)
| Skill | Level | Evidence |
|---|---|---|
| Incident response, root-cause analysis | C | Chakshi: 13 Jul outage fix; RCAs written from my device |
| Runbooks & technical documentation | C | Chakshi records (~880 files from my device) |
| Release smoke testing | C | Chakshi production browser smoke |
| Team leadership, customer operations | Stated | 5+ yrs hospitality (Operations Head, KSD Restaurants) |

---

## Projects the agent can now cite

| Project | Stack | Public? |
|---|---|---|
| News Article Classifier | DistilBERT, PyTorch, Transformers, Streamlit, AWS EC2/S3/RDS, PostgreSQL — 94.62% accuracy | GitHub |
| AI Lead Scoring System | XGBoost, scikit-learn, FastAPI, Docker, GitHub Actions, pytest (67 tests), React dashboard, Render + Vercel | GitHub |
| Mini Zia — business insight generator | pandas, anomaly detection, trend analysis, Claude/OpenAI rephrasing, Streamlit, CI | GitHub |
| Diabetes Risk Predictor | Flask, Random Forest, GridSearchCV, SQLite, PDF reports | GitHub |
| PowerPulse energy forecasting | LightGBM, XGBoost, Random Forest, time-series features | GitHub |
| Swiggy restaurant recommender | K-Means, cosine similarity, Streamlit | GitHub |
| Redbus scraping pipeline | Selenium, MySQL, SQLAlchemy, Streamlit | GitHub |
| Hotel ML Platform | React, TypeScript, Vite, Tailwind, TanStack, Recharts | GitHub |
| LinkedIn MCP Server | MCP, FastAPI, SQLAlchemy/Alembic, Redis, Playwright, Claude API, Docker | Local only |
| Developer dashboard | Node/Express, git automation, state machine, 47 tests | Local only (contains Chakshi content) |

## Please confirm (flagged for review until you do)
1. ~~MLflow, SHAP, Power BI, Excel~~ — resolved 29 Oct: removed. Your GitHub profile README still shows a Power BI badge; consider removing it so your profile matches your applications.
2. Customer Health engine, Price Comparison agent, Sara — still unconfirmed, so they stay off resumes.
3. **Chakshi items (level C)**: Career-Audit asks you to confirm hands-on vs. directed for each. The agent words these as "worked on" and doesn't claim sole authorship.
4. **LinkedIn MCP server**: Career-Audit flags LinkedIn ToS risk and a `.env` with secrets in that folder. Keep it off public showcases until it's cleaned.
5. **Job title**: Career-Audit material describes engineering work (RAG, CI, security fixes). You chose "Technical Support Engineer" for forms; make sure it matches your offer letter.
