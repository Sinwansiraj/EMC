-- Job Agent — switch the intake to Supabase Auth (per-user ownership).
-- Each seeker row and resume belongs to the authenticated user who created it.
-- Anonymous access is removed; users see and manage only their own data. The
-- agent still reads everything with the service key (bypasses RLS).

-- 1. Ownership columns (default to the caller's auth.uid()).
alter table public.job_seekers add column if not exists owner uuid references auth.users(id) on delete cascade;
alter table public.resumes     add column if not exists owner uuid references auth.users(id) on delete cascade;
alter table public.job_seekers alter column owner set default auth.uid();
alter table public.resumes     alter column owner set default auth.uid();
create index if not exists ix_job_seekers_owner on public.job_seekers(owner);
create index if not exists ix_resumes_owner on public.resumes(owner);

-- 2. job_seekers: replace the public-insert policy with owner-scoped CRUD.
drop policy if exists "public insert job_seekers" on public.job_seekers;
drop policy if exists "own job_seekers select" on public.job_seekers;
drop policy if exists "own job_seekers insert" on public.job_seekers;
drop policy if exists "own job_seekers update" on public.job_seekers;
drop policy if exists "own job_seekers delete" on public.job_seekers;
create policy "own job_seekers select" on public.job_seekers for select to authenticated using (owner = auth.uid());
create policy "own job_seekers insert" on public.job_seekers for insert to authenticated with check (owner = auth.uid());
create policy "own job_seekers update" on public.job_seekers for update to authenticated using (owner = auth.uid()) with check (owner = auth.uid());
create policy "own job_seekers delete" on public.job_seekers for delete to authenticated using (owner = auth.uid());

-- 3. resumes: owner-scoped CRUD.
drop policy if exists "public insert resumes" on public.resumes;
drop policy if exists "own resumes select" on public.resumes;
drop policy if exists "own resumes insert" on public.resumes;
drop policy if exists "own resumes delete" on public.resumes;
create policy "own resumes select" on public.resumes for select to authenticated using (owner = auth.uid());
create policy "own resumes insert" on public.resumes for insert to authenticated with check (owner = auth.uid());
create policy "own resumes delete" on public.resumes for delete to authenticated using (owner = auth.uid());

-- 4. Storage: files live under <auth.uid()>/... ; only the owner may upload/read them.
drop policy if exists "anon upload resumes" on storage.objects;
drop policy if exists "own upload resumes" on storage.objects;
drop policy if exists "own read resumes" on storage.objects;
create policy "own upload resumes" on storage.objects for insert to authenticated
  with check (bucket_id = 'resumes' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "own read resumes" on storage.objects for select to authenticated
  using (bucket_id = 'resumes' and (storage.foldername(name))[1] = auth.uid()::text);
