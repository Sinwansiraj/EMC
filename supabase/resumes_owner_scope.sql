-- Job Agent — harden the resumes INSERT policy (owner + seeker + file scope).
--
-- Background: auth.sql made resume rows owner-scoped with `owner = auth.uid()`
-- (the column defaults to auth.uid()). That proves the ROW belongs to the
-- caller, but it does NOT constrain `seeker_id`: a caller could insert a row
-- they own while pointing `seeker_id` at ANOTHER user's job_seeker. The agent's
-- fetch_seekers() groups resumes by seeker_id, so such a row would be treated as
-- the victim's resume and could mark the victim "ready" with attacker material.
--
-- This migration replaces the INSERT policy so a resume can only be created when:
--   1. the row is owned by the caller                (owner        = auth.uid())
--   2. it links to a seeker the caller owns          (seeker_id    -> own job_seeker)
--   3. its stored file lives in the caller's folder  (file_path    starts with auth.uid()/)
-- (3) mirrors the storage upload policy from auth.sql so the DB row and the
-- Storage object can never diverge across users.
--
-- Idempotent: safe to run more than once. SELECT/DELETE policies from auth.sql
-- are already owner-scoped and are left unchanged.

alter table public.resumes enable row level security;

-- Drop every prior INSERT policy, including the anon-era permissive one, so the
-- scoped policy below is authoritative and no `with check (true)` rule survives.
drop policy if exists "public insert resumes" on public.resumes;
drop policy if exists "own resumes insert"    on public.resumes;

create policy "own resumes insert" on public.resumes
  for insert to authenticated
  with check (
    owner = auth.uid()
    and exists (
      select 1
      from public.job_seekers js
      where js.id = resumes.seeker_id
        and js.owner = auth.uid()
    )
    and split_part(file_path, '/', 1) = auth.uid()::text
  );
