-- Job Agent — per-role resumes
-- A seeker targets one or more roles and must attach a resume for EACH targeted
-- role; only then will the agent apply. Files live in a PRIVATE Storage bucket;
-- this table records which role each uploaded resume targets.
--
-- `target_role` uses the agent's own role-family codes so a resume maps directly
-- onto tailor.py's documents.master_resumes[<family>].

create table if not exists public.resumes (
  id          uuid primary key default gen_random_uuid(),
  seeker_id   uuid not null references public.job_seekers(id) on delete cascade,
  target_role text not null,
  file_path   text not null,          -- object path inside the 'resumes' bucket
  file_name   text,
  created_at  timestamptz not null default now()
);

alter table public.resumes enable row level security;

-- anon may INSERT a resume row, but cannot read anyone's rows back.
drop policy if exists "public insert resumes" on public.resumes;
create policy "public insert resumes" on public.resumes
  for insert to anon with check (true);

create index if not exists ix_resumes_seeker on public.resumes(seeker_id);

-- Private Storage bucket for the resume files themselves.
insert into storage.buckets (id, name, public)
  values ('resumes', 'resumes', false)
  on conflict (id) do nothing;

-- anon may UPLOAD into the 'resumes' bucket, but there is no SELECT policy, so
-- files are not publicly downloadable. The agent reads them with the service key.
drop policy if exists "anon upload resumes" on storage.objects;
create policy "anon upload resumes" on storage.objects
  for insert to anon with check (bucket_id = 'resumes');
