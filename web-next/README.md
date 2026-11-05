# EMC Web — Next.js + Supabase

The user-facing product for the Job Agent (**EMC — Error Makes Clever**):

- a **landing page** (public),
- **accounts** with email verification + password sign-in,
- a **job-hunt intake** where each user adds target roles and a resume per role,
- a **read-only dashboard** mirroring the agent's activity (jobs, applications, stats).

Only the landing and auth pages are public; everything else requires sign-in.

## Architecture

```
Python agent ──(local SQLite = source of truth)
   │  sync-supabase  (service key, privacy-filtered mirror)
   ▼
Supabase ── Auth (email OTP + password) · Postgres + RLS · Storage (private resumes)
   ▲  anon / publishable key (RLS-gated)
Next.js (this app) — landing · /login · /dashboard · /jobs · /applications · /get-started
```

Two RLS contracts:
- **Showcase tables** (`jobs`, `applications`, `stats`): public **read** only — a privacy-filtered mirror (no form answers, no profile, no audit detail).
- **User tables** (`job_seekers`, `resumes`) + Storage: per-user, owner = `auth.uid()`. A user reads/writes **only their own** rows; cross-user reads return nothing; a spoofed-`owner` insert is rejected (403). The agent reads everything with the service key (bypasses RLS).

## Authentication

- **Create account** — name, phone, email, password → an **8-digit code** is emailed → verify → signed in. Name & phone are stored as `user_metadata` and prefill the intake form.
- **Sign in** — email + password.
- Routes: landing `/`, `/login` (sign in / create account toggle, `?mode=signup`), `/auth/confirm` (email-link fallback), protected `/dashboard` `/jobs` `/applications` `/get-started`.

> **Email delivery requires custom SMTP.** Supabase's free built-in email is rate-limited (a few/hour) and can't carry an OTP code. This project uses **Brevo** SMTP (configured in Supabase → Authentication → SMTP Settings), which also unlocks the email templates that include the `{{ .Token }}` code.

## Local development

```bash
cp .env.local.example .env.local      # public, browser-safe keys only
npm install
npm run dev                           # http://localhost:3000
```

Populate the mirror dashboard from the Python side:

```bash
# repo root, venv active, private/.env holding the writer keys
python -m job_agent seed-demo         # synthetic showcase data (optional)
python -m job_agent sync-supabase     # push read-models to Supabase
```

## Environment variables

| Variable | Where | Secret? |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | this app (`.env.local`, Vercel) | no |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | this app (`.env.local`, Vercel) | no — gated by RLS |
| `SUPABASE_SERVICE_ROLE_KEY` | **Python agent only** (`private/.env`) | **yes — never commit, never put in this app** |

Supabase dashboard also needs: **SMTP** (Brevo) configured, and **URL Configuration** → Site URL + Redirect URLs (`https://<prod-domain>/**` and `http://localhost:3000/**`).

## Database schema (run once in Supabase SQL Editor)

| File | Creates |
|---|---|
| [`../supabase/schema.sql`](../supabase/schema.sql) | showcase tables (public read) |
| [`../supabase/intake.sql`](../supabase/intake.sql) | `job_seekers` base table |
| [`../supabase/resumes.sql`](../supabase/resumes.sql) | per-role `resumes` + private Storage bucket |
| [`../supabase/auth.sql`](../supabase/auth.sql) | ownership columns + per-user RLS |

## Deploy on Vercel

1. Import the repo, set **Root Directory** to `web-next`.
2. Add the two `NEXT_PUBLIC_*` variables in Project Settings → Environment Variables.
3. Deploy, then set the Supabase **Site URL** to the production domain.

The agent's readiness gate — `python -m job_agent seekers` — lists each consented user and whether every targeted role has a resume (**READY / BLOCKED**).

> Still to build: the per-user agent run that pulls a READY user's resumes and actually searches/applies for them; password reset; Brevo domain authentication.
