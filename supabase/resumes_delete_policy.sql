-- Job Agent — allow a user to delete their OWN resume files from Storage.
--
-- auth.sql granted authenticated users insert + select on the 'resumes' bucket
-- (scoped to their own `auth.uid()/…` folder) but no delete. Resume Studio now
-- retires a replaced resume (and cleans up a file whose row insert failed), so
-- the owner needs delete on their own objects. The resumes TABLE already has an
-- owner-scoped delete policy ("own resumes delete" in auth.sql); this adds the
-- matching Storage policy. Idempotent.

drop policy if exists "own delete resumes" on storage.objects;
create policy "own delete resumes" on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'resumes'
    and (storage.foldername(name))[1] = auth.uid()::text
  );
