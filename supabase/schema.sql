-- Job Agent — Supabase showcase mirror schema
-- Run this once in your Supabase project: Dashboard -> SQL Editor -> paste -> Run.
--
-- These are READ-ONLY public mirror tables for the portfolio showcase. The local
-- Python agent (service_role, via the connection string) is the only writer; the
-- Next.js frontend reads them with the anon/publishable key under RLS.
--
-- Privacy: this mirror intentionally carries NO raw form answers, profile data, or
-- audit detail — only job postings, application status, and a dashboard snapshot.

create table if not exists public.jobs (
  id             bigint primary key,
  score          real,
  role_family    text,
  title          text not null,
  company        text not null,
  location       text,
  platform       text,
  remote         boolean default false,
  filter_reason  text,
  deadline       text,
  salary_min     integer,
  salary_max     integer,
  url            text,
  status         text,
  missing        jsonb default '[]'::jsonb,
  first_seen_at  timestamptz
);

create table if not exists public.applications (
  id               bigint primary key,
  job_id           bigint,
  status           text,
  resume_version   text,
  selection_reason text,
  approval         text,
  submitted_at     timestamptz,
  follow_up_on     text,
  verification     text,
  title            text,
  company          text,
  platform         text,
  score            real,
  url              text
);

-- Single-row dashboard snapshot (counts, performance, follow-ups) as JSON.
create table if not exists public.stats (
  id           int primary key default 1,
  data         jsonb not null,
  captured_at  timestamptz not null default now(),
  constraint stats_single_row check (id = 1)
);

-- Row-Level Security: enable everywhere, then allow ONLY public SELECT.
-- No INSERT/UPDATE/DELETE policy exists, so the anon key cannot write;
-- the service_role used by the agent bypasses RLS for the sync.
alter table public.jobs         enable row level security;
alter table public.applications enable row level security;
alter table public.stats        enable row level security;

drop policy if exists "public read jobs"         on public.jobs;
drop policy if exists "public read applications"  on public.applications;
drop policy if exists "public read stats"         on public.stats;

create policy "public read jobs"        on public.jobs         for select to anon using (true);
create policy "public read applications" on public.applications for select to anon using (true);
create policy "public read stats"        on public.stats        for select to anon using (true);

create index if not exists ix_jobs_status on public.jobs(status);
create index if not exists ix_apps_status on public.applications(status);
