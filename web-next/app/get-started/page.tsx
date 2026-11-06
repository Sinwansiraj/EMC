"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/utils/supabase/client";
import { Card, PageHead } from "@/components/ui";

// Role options mirror the agent's role families (job_agent/tailor.py FAMILY_FOCUS),
// so each uploaded resume maps straight onto the agent's per-family master resume.
const ROLES: { code: string; label: string }[] = [
  { code: "data_analyst", label: "Data Analyst" },
  { code: "data_scientist", label: "Data Scientist" },
  { code: "ai_ml_engineer", label: "AI / ML Engineer" },
  { code: "ai_builder", label: "AI Builder" },
  { code: "prompt_engineer", label: "Prompt Engineer" },
  { code: "customer_support_mgmt", label: "Customer Support (Management)" },
  { code: "customer_support_engineer", label: "Customer Support Engineer" },
];

type Base = {
  full_name: string; email: string; phone: string;
  preferred_locations: string; work_mode: string; experience_years: string;
  expected_salary: string; linkedin_url: string; portfolio_url: string;
  github_url: string; notes: string;
};
const EMPTY: Base = {
  full_name: "", email: "", phone: "", preferred_locations: "", work_mode: "any",
  experience_years: "", expected_salary: "", linkedin_url: "", portfolio_url: "",
  github_url: "", notes: "",
};

type Entry = { role: string; file: File | null };

const STEPS = ["About you", "Roles & resumes", "Review & consent"];

function labelFor(code: string) {
  return ROLES.find((r) => r.code === code)?.label ?? code;
}

export default function GetStarted() {
  const [step, setStep] = useState(0);
  const [base, setBase] = useState<Base>(EMPTY);
  const [entries, setEntries] = useState<Entry[]>([{ role: "data_analyst", file: null }]);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string[] | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      if (data.user) {
        const meta = data.user.user_metadata || {};
        setUserEmail(data.user.email ?? null);
        setBase((b) => ({
          ...b,
          full_name: b.full_name || meta.full_name || "",
          phone: b.phone || meta.phone || "",
          email: b.email || data.user!.email || "",
        }));
      }
    });
  }, []);

  const set = (k: keyof Base) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setBase((b) => ({ ...b, [k]: e.target.value }));

  const usedRoles = entries.map((e) => e.role);
  const availableFor = (current: string) =>
    ROLES.filter((r) => r.code === current || !usedRoles.includes(r.code));

  function addEntry() {
    const free = ROLES.find((r) => !usedRoles.includes(r.code));
    if (free) setEntries((es) => [...es, { role: free.code, file: null }]);
  }
  function removeEntry(i: number) {
    setEntries((es) => es.filter((_, idx) => idx !== i));
  }
  function setRole(i: number, role: string) {
    setEntries((es) => es.map((e, idx) => (idx === i ? { ...e, role } : e)));
  }
  function setFile(i: number, file: File | null) {
    setEntries((es) => es.map((e, idx) => (idx === i ? { ...e, file } : e)));
  }

  // --- per-step validation; returns true when the step is OK to leave ----
  function validateStep(s: number): string | null {
    if (s === 0) {
      if (!base.full_name.trim() || !base.email.trim()) return "Name and email are required.";
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(base.email.trim())) return "Enter a valid email address.";
      if (base.experience_years) {
        const yrs = Number(base.experience_years);
        if (!Number.isFinite(yrs) || yrs < 0) return "Years of experience must be zero or more.";
      }
    }
    if (s === 1) {
      const complete = entries.filter((en) => en.role && en.file);
      if (complete.length === 0) return "Add at least one target role with a resume.";
      const missing = entries.filter((en) => en.role && !en.file);
      if (missing.length)
        return `Attach a resume for every targeted role — missing: ${missing.map((m) => labelFor(m.role)).join(", ")}. The agent only applies to a role once it has a matching resume.`;
    }
    return null;
  }

  function next() {
    const err = validateStep(step);
    if (err) { setError(err); return; }
    setError(null);
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  }
  function back() {
    setError(null);
    setStep((s) => Math.max(s - 1, 0));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    // Re-run both data steps' validation before writing.
    const err = validateStep(0) || validateStep(1);
    if (err) { setError(err); return; }
    if (!consent) {
      setError("Please give permission for the agent to search and apply on your behalf.");
      return;
    }

    setBusy(true);
    const supabase = createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) { setBusy(false); setError("Please sign in again."); return; }
    const targetRoles = entries.map((en) => en.role).join(", ");
    const payload = {
      full_name: base.full_name,
      email: base.email,
      phone: base.phone || null,
      target_roles: targetRoles,
      preferred_locations: base.preferred_locations || null,
      work_mode: base.work_mode,
      experience_years: base.experience_years ? Number(base.experience_years) : null,
      expected_salary: base.expected_salary || null,
      linkedin_url: base.linkedin_url || null,
      portfolio_url: base.portfolio_url || null,
      github_url: base.github_url || null,
      notes: base.notes || null,
      consent: true,
    };

    // Update the existing profile if the user already has one, so re-running
    // onboarding to edit roles doesn't create a duplicate seeker. owner defaults
    // to auth.uid() via RLS and the owner can read/update their own rows.
    const { data: existing, error: exErr } = await supabase
      .from("job_seekers").select("id").order("created_at", { ascending: false }).limit(1);
    if (exErr) { setBusy(false); setError(exErr.message); return; }

    let seekerId: string;
    if (existing && existing.length) {
      seekerId = existing[0].id;
      const { error: updErr } = await supabase.from("job_seekers").update(payload).eq("id", seekerId);
      if (updErr) { setBusy(false); setError(updErr.message); return; }
    } else {
      const { data: seeker, error: seekErr } = await supabase
        .from("job_seekers").insert(payload).select("id").single();
      if (seekErr || !seeker) { setBusy(false); setError(seekErr?.message || "Could not save details."); return; }
      seekerId = seeker.id;
    }

    for (const en of entries) {
      const file = en.file!;
      const safe = file.name.replace(/[^\w.\-]+/g, "_");
      // Storage path must start with the user's id (enforced by the storage RLS policy).
      const path = `${user.id}/${en.role}/${Date.now()}-${safe}`;
      const up = await supabase.storage.from("resumes").upload(path, file, { upsert: true });
      if (up.error) { setBusy(false); setError(`Upload failed for ${labelFor(en.role)}: ${up.error.message}`); return; }
      const { error: rErr } = await supabase.from("resumes").insert({
        seeker_id: seekerId, target_role: en.role, file_path: path, file_name: file.name,
      });
      if (rErr) { setBusy(false); setError(rErr.message); return; }
    }

    setBusy(false);
    setDone(entries.map((en) => labelFor(en.role)));
  }

  if (done) {
    return (
      <div className="success">
        <h2>You&apos;re all set 🎉</h2>
        <p>Thanks, {base.full_name.split(" ")[0]}. We saved your details and a resume for each role
          you&apos;re targeting: <b>{done.join(", ")}</b>.</p>
        <p>With your permission, the agent will match each resume to its role and start finding and
          preparing applications for your review.</p>
        <p className="note">Your details and files are stored privately — only you can read them;
          they are never visible to other visitors.</p>
        <div className="cluster" style={{ marginTop: 16 }}>
          <Link className="btn" href="/dashboard">Go to your dashboard →</Link>
          <Link className="btn ghost" href="/jobs">Browse jobs</Link>
        </div>
      </div>
    );
  }

  return (
    <>
      <PageHead
        title="Get started"
        subtitle="Add a resume for each role you want the agent to apply to."
        actions={userEmail ? <span className="chip outline">signed in as {userEmail}</span> : undefined}
      />

      {/* Step indicator */}
      <div className="steps" role="list">
        {STEPS.map((label, i) => (
          <div key={label} role="listitem" className={`step ${i === step ? "on" : i < step ? "done" : ""}`} aria-current={i === step ? "step" : undefined}>
            <span className="n">{i < step ? "✓" : i + 1}</span>
            {label}
          </div>
        ))}
      </div>

      <form onSubmit={submit}>
        {/* STEP 1 — About you */}
        {step === 0 ? (
          <Card>
            <div className="form-grid">
              <div>
                <label className="field" htmlFor="full_name">Full name <span className="req">*</span></label>
                <input id="full_name" value={base.full_name} onChange={set("full_name")} required />
              </div>
              <div>
                <label className="field" htmlFor="email">Email <span className="req">*</span></label>
                <input id="email" type="email" value={base.email} onChange={set("email")} required />
              </div>
              <div>
                <label className="field" htmlFor="phone">Phone</label>
                <input id="phone" value={base.phone} onChange={set("phone")} />
              </div>
              <div>
                <label className="field" htmlFor="locs">Preferred locations</label>
                <input id="locs" value={base.preferred_locations} onChange={set("preferred_locations")} placeholder="e.g. Bengaluru, Remote" />
              </div>
              <div>
                <label className="field" htmlFor="work_mode">Work mode</label>
                <select id="work_mode" value={base.work_mode} onChange={set("work_mode")}>
                  <option value="any">Any</option>
                  <option value="remote">Remote</option>
                  <option value="hybrid">Hybrid</option>
                  <option value="onsite">Onsite</option>
                </select>
              </div>
              <div>
                <label className="field" htmlFor="exp">Years of experience</label>
                <input id="exp" type="number" min="0" step="0.5" value={base.experience_years} onChange={set("experience_years")} />
              </div>
              <div>
                <label className="field" htmlFor="sal">Expected salary</label>
                <input id="sal" value={base.expected_salary} onChange={set("expected_salary")} placeholder="e.g. 12 LPA" />
              </div>
              <div>
                <label className="field" htmlFor="li">LinkedIn URL</label>
                <input id="li" value={base.linkedin_url} onChange={set("linkedin_url")} placeholder="https://linkedin.com/in/…" />
              </div>
              <div>
                <label className="field" htmlFor="pf">Portfolio URL</label>
                <input id="pf" value={base.portfolio_url} onChange={set("portfolio_url")} />
              </div>
              <div>
                <label className="field" htmlFor="gh">GitHub URL</label>
                <input id="gh" value={base.github_url} onChange={set("github_url")} />
              </div>
              <div className="field-full">
                <label className="field" htmlFor="notes">Anything else the agent should know?</label>
                <textarea id="notes" value={base.notes} onChange={set("notes")} placeholder="Constraints, must-haves, companies to avoid…" />
              </div>
            </div>
          </Card>
        ) : null}

        {/* STEP 2 — Roles & resumes */}
        {step === 1 ? (
          <Card>
            <p className="note mt-0">
              Add every role you want to apply for and attach a tailored resume for each. The agent
              applies to a role <b>only</b> when it has a matching resume.
            </p>
            {entries.map((en, i) => (
              <div key={i} className="entry-row">
                <div>
                  <label className="field">Target role</label>
                  <select value={en.role} onChange={(e) => setRole(i, e.target.value)}>
                    {availableFor(en.role).map((r) => (
                      <option key={r.code} value={r.code}>{r.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="field">Resume {en.file ? "✓" : ""}</label>
                  <input type="file" accept=".pdf,.doc,.docx"
                    onChange={(e) => setFile(i, e.target.files?.[0] ?? null)} />
                </div>
                <div>
                  {entries.length > 1 ? (
                    <button type="button" className="btn subtle" onClick={() => removeEntry(i)}>Remove</button>
                  ) : null}
                </div>
              </div>
            ))}
            {entries.length < ROLES.length ? (
              <button type="button" className="btn ghost" onClick={addEntry}>+ Add another role</button>
            ) : null}
          </Card>
        ) : null}

        {/* STEP 3 — Review & consent */}
        {step === 2 ? (
          <div className="stack">
            <Card>
              <h3>Your details</h3>
              <div className="row"><span className="muted">Name</span><b>{base.full_name || "—"}</b></div>
              <div className="row"><span className="muted">Email</span><b>{base.email || "—"}</b></div>
              <div className="row"><span className="muted">Phone</span><b>{base.phone || "—"}</b></div>
              <div className="row"><span className="muted">Preferred locations</span><b>{base.preferred_locations || "—"}</b></div>
              <div className="row"><span className="muted">Work mode</span><b style={{ textTransform: "capitalize" }}>{base.work_mode}</b></div>
              <div className="row"><span className="muted">Experience</span><b>{base.experience_years ? `${base.experience_years} yrs` : "—"}</b></div>
              <div className="row"><span className="muted">Expected salary</span><b>{base.expected_salary || "—"}</b></div>
            </Card>
            <Card>
              <h3>Target roles &amp; resumes</h3>
              {entries.map((en, i) => (
                <div className="row" key={i}>
                  <span>{labelFor(en.role)}</span>
                  <span className={en.file ? "pill good" : "pill warn"}>{en.file ? en.file.name : "no resume"}</span>
                </div>
              ))}
            </Card>
            <label className="consent">
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              <span className="note">
                I give the Job Agent permission to search for jobs matching these roles and to prepare
                applications, using the matching resume for each role, for my review. <b>Nothing is
                submitted without my approval.</b>
              </span>
            </label>
          </div>
        ) : null}

        {error ? <div className="error">{error}</div> : null}

        <div className="wizard-nav">
          {step > 0 ? (
            <button type="button" className="btn ghost" onClick={back} disabled={busy}>← Back</button>
          ) : null}
          <div className="spacer" />
          {step < STEPS.length - 1 ? (
            <button type="button" className="btn" onClick={next}>Continue →</button>
          ) : (
            <button className="btn" type="submit" disabled={busy || !consent}>
              {busy ? "Uploading…" : "Submit details & resumes"}
            </button>
          )}
        </div>
      </form>
    </>
  );
}
