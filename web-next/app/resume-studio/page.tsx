"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { createClient } from "@/utils/supabase/client";
import { Card, PageHead, EmptyState, ErrorState, Skeleton, Chip } from "@/components/ui";

// Must match the agent's role families (job_agent/tailor.py) — same list the
// onboarding wizard uses, so a resume maps onto the agent's per-family master.
const ROLES: { code: string; label: string }[] = [
  { code: "data_analyst", label: "Data Analyst" },
  { code: "data_scientist", label: "Data Scientist" },
  { code: "ai_ml_engineer", label: "AI / ML Engineer" },
  { code: "ai_builder", label: "AI Builder" },
  { code: "prompt_engineer", label: "Prompt Engineer" },
  { code: "customer_support_mgmt", label: "Customer Support (Management)" },
  { code: "customer_support_engineer", label: "Customer Support Engineer" },
];
const labelFor = (code: string) => ROLES.find((r) => r.code === code)?.label ?? code;

type Resume = {
  id: string;
  target_role: string;
  file_path: string;
  file_name: string | null;
  created_at: string;
};

export default function ResumeStudio() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [signedIn, setSignedIn] = useState<boolean>(true);
  const [hasProfile, setHasProfile] = useState<boolean>(false);
  const [seekerId, setSeekerId] = useState<string | null>(null);
  const [targetRoles, setTargetRoles] = useState<string[]>([]);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [busyRole, setBusyRole] = useState<string | null>(null);
  // Guards against an older refresh resolving after a newer one and clobbering state.
  const loadSeq = useRef(0);

  const load = useCallback(async () => {
    const seq = ++loadSeq.current;
    setLoading(true);
    setError(null);
    const supabase = createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (seq !== loadSeq.current) return;
    if (!user) { setSignedIn(false); setLoading(false); return; }

    // Owner-scoped reads (RLS: owner = auth.uid()).
    const [seekersRes, resumesRes] = await Promise.all([
      supabase.from("job_seekers").select("id,target_roles").order("created_at", { ascending: false }),
      supabase.from("resumes").select("id,target_role,file_path,file_name,created_at").order("created_at", { ascending: false }),
    ]);

    // A newer load() started while we awaited — drop this stale result.
    if (seq !== loadSeq.current) return;
    if (seekersRes.error) { setError(seekersRes.error.message); setLoading(false); return; }
    if (resumesRes.error) { setError(resumesRes.error.message); setLoading(false); return; }

    const seekers = seekersRes.data ?? [];
    setHasProfile(seekers.length > 0);
    setSeekerId(seekers[0]?.id ?? null);
    const roles = new Set<string>();
    for (const s of seekers) {
      for (const r of String(s.target_roles ?? "").split(",").map((x) => x.trim()).filter(Boolean)) {
        roles.add(r);
      }
    }
    // Also surface any role that only has a resume, so nothing is hidden.
    for (const r of resumesRes.data ?? []) roles.add(r.target_role);

    setTargetRoles(Array.from(roles));
    setResumes((resumesRes.data as Resume[]) ?? []);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  async function download(path: string) {
    // Open the tab synchronously inside the click so the browser keeps the user
    // activation; navigate it once the signed URL is ready. Popup-blocked → fall
    // back to a direct open.
    const win = window.open("about:blank", "_blank");
    if (win) { try { win.opener = null; } catch { /* ignore */ } }
    const supabase = createClient();
    const { data, error } = await supabase.storage.from("resumes").createSignedUrl(path, 60);
    if (error || !data) {
      if (win) win.close();
      setError(error?.message || "Could not create a download link.");
      return;
    }
    if (win) win.location.replace(data.signedUrl);
    else window.open(data.signedUrl, "_blank", "noopener,noreferrer");
  }

  async function upload(role: string, file: File | null) {
    if (!file) return;
    setBusyRole(role);
    setError(null);
    setNotice(null);
    const supabase = createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) { setBusyRole(null); setSignedIn(false); return; }
    if (!seekerId) {
      setBusyRole(null);
      setError("Add your profile first so resumes can be linked to it.");
      return;
    }
    // Resumes already on file for this role — retired after the new one lands so
    // each role keeps exactly one active resume.
    const prior = resumes.filter((r) => r.target_role === role);

    const safe = file.name.replace(/[^\w.\-]+/g, "_");
    const path = `${user.id}/${role}/${Date.now()}-${safe}`;
    const up = await supabase.storage.from("resumes").upload(path, file, { upsert: true });
    if (up.error) { setBusyRole(null); setError(`Upload failed: ${up.error.message}`); return; }
    const { error: rErr } = await supabase.from("resumes").insert({
      seeker_id: seekerId, target_role: role, file_path: path, file_name: file.name,
    });
    if (rErr) {
      // Don't leave an orphaned file with no row behind.
      await supabase.storage.from("resumes").remove([path]).catch(() => {});
      setBusyRole(null);
      setError(rErr.message);
      return;
    }

    // Retire the previous resume(s) for this role: delete the rows (owner-scoped)
    // and best-effort remove their files (needs the storage delete policy).
    if (prior.length) {
      await supabase.from("resumes").delete().in("id", prior.map((r) => r.id));
      await supabase.storage.from("resumes").remove(prior.map((r) => r.file_path)).catch(() => {});
    }

    setNotice(prior.length ? `Replaced the resume for ${labelFor(role)}.` : `Uploaded a new resume for ${labelFor(role)}.`);
    setBusyRole(null);
    await load();
  }

  const byRole = (role: string) => resumes.filter((r) => r.target_role === role);

  if (!signedIn) {
    return (
      <>
        <PageHead title="Resume Studio" />
        <ErrorState title="Please sign in">
          <Link href="/login">Sign in</Link> to manage your resumes.
        </ErrorState>
      </>
    );
  }

  return (
    <>
      <PageHead
        title="Resume Studio"
        subtitle="Manage a tailored resume for each role you target. The agent applies to a role only when it has a matching resume."
        actions={<Link className="btn ghost sm" href="/get-started">Edit profile & roles</Link>}
      />

      {error ? <div className="error" style={{ marginBottom: 14 }}>{error}</div> : null}
      {notice ? <div className="note" style={{ color: "var(--good)", marginBottom: 14 }}>{notice}</div> : null}

      {loading ? (
        <div className="stack">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}><Skeleton className="sk-line w-40" /><Skeleton className="sk-line w-80" /></Card>
          ))}
        </div>
      ) : !hasProfile && resumes.length === 0 ? (
        <EmptyState
          icon="📄"
          title="No resumes yet"
          action={<Link className="btn" href="/get-started">Set up your job hunt →</Link>}
        >
          Add your target roles and a resume for each in the onboarding wizard.
        </EmptyState>
      ) : (
        <>
          {/* Coverage summary */}
          <Card style={{ marginBottom: 16 }}>
            <h3>Coverage</h3>
            <div className="cluster">
              {targetRoles.length === 0 ? (
                <span className="muted">No target roles yet — add some in your profile.</span>
              ) : (
                targetRoles.map((role) => {
                  const has = byRole(role).length > 0;
                  return (
                    <span key={role} className={has ? "pill good" : "pill warn"}>
                      {labelFor(role)}{has ? "" : " · needs resume"}
                    </span>
                  );
                })
              )}
            </div>
            <p className="note mb-0" style={{ marginTop: 12 }}>
              Uploading a resume marks a role <b>ready</b> and stores the file privately for your review.
              When the local agent prepares an application it tailors from its own configured master
              resume for that role family — syncing an uploaded file into a run is a manual, agent-side step.
            </p>
          </Card>

          {/* Per-role management */}
          <div className="stack">
            {targetRoles.map((role) => {
              const list = byRole(role);
              return (
                <Card key={role}>
                  <div className="cluster" style={{ justifyContent: "space-between" }}>
                    <h3 style={{ margin: 0 }}>{labelFor(role)}</h3>
                    <Chip variant="outline">{list.length} resume{list.length === 1 ? "" : "s"}</Chip>
                  </div>

                  {list.length === 0 ? (
                    <p className="muted" style={{ margin: "12px 0" }}>No resume for this role yet.</p>
                  ) : (
                    <div style={{ marginTop: 10 }}>
                      {list.map((r) => (
                        <div className="row" key={r.id}>
                          <span style={{ minWidth: 0 }}>
                            <b style={{ wordBreak: "break-word" }}>{r.file_name || r.file_path.split("/").pop()}</b>
                            <div className="faint" style={{ fontSize: 12 }}>
                              added {new Date(r.created_at).toLocaleDateString(undefined, { dateStyle: "medium" })}
                            </div>
                          </span>
                          <button className="btn ghost sm" onClick={() => download(r.file_path)}>Download</button>
                        </div>
                      ))}
                    </div>
                  )}

                  <div style={{ marginTop: 14 }}>
                    <label className="field" htmlFor={`up-${role}`}>
                      {list.length ? "Replace with a new resume" : "Upload a resume"}
                    </label>
                    <input
                      id={`up-${role}`}
                      type="file"
                      accept=".pdf,.doc,.docx"
                      disabled={busyRole === role}
                      onChange={(e) => upload(role, e.target.files?.[0] ?? null)}
                    />
                    {busyRole === role ? <p className="note">Uploading…</p> : null}
                  </div>
                </Card>
              );
            })}
          </div>
        </>
      )}
    </>
  );
}
