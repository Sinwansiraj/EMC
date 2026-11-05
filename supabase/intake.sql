-- Job Agent — user intake (write-only collection)
-- Collects each visitor's job-hunt details from the public frontend into Supabase.
-- Unlike the showcase tables (public READ), this table is public INSERT only:
-- the anon key can add a submission but can NEVER read anyone's rows back, so the
-- personal details stay private. The agent reads them later with the service key
-- (bypasses RLS) — only for users who gave consent.

create table if not exists public.job_seekers (
  id                 uuid primary key default gen_random_uuid(),
  created_at         timestamptz not null default now(),
  full_name          text not null,
  email              text not null,
  phone              text,
  current_title      text,
  target_roles       text,
  preferred_locations text,
  work_mode          text,            -- remote | hybrid | onsite | any
  experience_years   numeric,
  expected_salary    text,
  linkedin_url       text,
  portfolio_url      text,
  github_url         text,
  resume_url         text,            -- link for now; file upload = Supabase Storage (later)
  cover_letter_url   text,
  notes              text,
  consent            boolean not null default false,  -- permission for the agent to act
  status             text not null default 'new'      -- new | queued | searching | done
);

alter table public.job_seekers enable row level security;

-- Anyone may submit; consent must be explicitly granted in the row.
drop policy if exists "public insert job_seekers" on public.job_seekers;
create policy "public insert job_seekers"
  on public.job_seekers for insert to anon
  with check (consent = true);

-- No SELECT/UPDATE/DELETE policy for anon  => submissions are not readable from the
-- browser. The service_role used by the agent bypasses RLS to read permitted rows.
