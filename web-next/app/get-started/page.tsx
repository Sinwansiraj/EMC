"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/utils/supabase/client";

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

function labelFor(code: string) {
  return ROLES.find((r) => r.code === code)?.label ?? code;
}

export default function GetStarted() {
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

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!base.full_name.trim() || !base.email.trim()) {
      setError("Name and email are required.");
      return;
    }
    const complete = entries.filter((en) => en.role && en.file);
    if (complete.length === 0) {
      setError("Add at least one target role with a resume.");
      return;
    }
    const missing = entries.filter((en) => en.role && !en.file);
    if (missing.length) {
      setError(
        `Attach a resume for every targeted role — missing: ${missing.map((m) => labelFor(m.role)).join(", ")}. ` +
          "The agent only applies to a role once it has a matching resume.",
      );
      return;
    }
    if (!consent) {
      setError("Please give permission for the agent to search and apply on your behalf.");
      return;
    }

    setBusy(true);
    const supabase = createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) { setBusy(false); setError("Please sign in again."); return; }
    const targetRoles = entries.map((en) => en.role).join(", ");

    // owner defaults to auth.uid() via RLS; select the new id back (owner can read own rows).
    const { data: seeker, error: seekErr } = await supabase.from("job_seekers").insert({
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
    }).select("id").single();
    if (seekErr || !seeker) { setBusy(false); setError(seekErr?.message || "Could not save details."); return; }

    for (const en of entries) {
      const file = en.file!;
      const safe = file.name.replace(/[^\w.\-]+/g, "_");
      // Storage path must start with the user's id (enforced by the storage RLS policy).
      const path = `${user.id}/${en.role}/${Date.now()}-${safe}`;
      const up = await supabase.storage.from("resumes").upload(path, file, { upsert: true });
      if (up.error) { setBusy(false); setError(`Upload failed for ${labelFor(en.role)}: ${up.error.message}`); return; }
      const { error: rErr } = await supabase.from("resumes").insert({
        seeker_id: seeker.id, target_role: en.role, file_path: path, file_name: file.name,
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
        <p className="note">Your details and files are stored privately — write-only from this page,
          never readable by other visitors.</p>
      </div>
    );
  }

  return (
    <>
      <h2 className="section">
        Get started<span className="sub">add a resume for each role you want the agent to apply to</span>
        {userEmail ? <span className="sub" style={{ marginLeft: "auto" }}>signed in as {userEmail}</span> : null}
      </h2>
      <form className="card" onSubmit={submit}>
        <div className="form-grid">
          <div>
            <label className="field">Full name <span className="req">*</span></label>
            <input value={base.full_name} onChange={set("full_name")} required />
          </div>
          <div>
            <label className="field">Email <span className="req">*</span></label>
            <input type="email" value={base.email} onChange={set("email")} required />
          </div>
          <div>
            <label className="field">Phone</label>
            <input value={base.phone} onChange={set("phone")} />
          </div>
          <div>
            <label className="field">Preferred locations</label>
            <input value={base.preferred_locations} onChange={set("preferred_locations")} placeholder="e.g. Bengaluru, Remote" />
          </div>
          <div>
            <label className="field">Work mode</label>
            <select value={base.work_mode} onChange={set("work_mode")}>
              <option value="any">Any</option>
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">Onsite</option>
            </select>
          </div>
          <div>
            <label className="field">Years of experience</label>
            <input type="number" min="0" step="0.5" value={base.experience_years} onChange={set("experience_years")} />
          </div>
          <div>
            <label className="field">Expected salary</label>
            <input value={base.expected_salary} onChange={set("expected_salary")} placeholder="e.g. 12 LPA" />
          </div>
          <div>
            <label className="field">LinkedIn URL</label>
            <input value={base.linkedin_url} onChange={set("linkedin_url")} placeholder="https://linkedin.com/in/…" />
          </div>
          <div>
            <label className="field">Portfolio URL</label>
            <input value={base.portfolio_url} onChange={set("portfolio_url")} />
          </div>
          <div>
            <label className="field">GitHub URL</label>
            <input value={base.github_url} onChange={set("github_url")} />
          </div>
          <div className="field-full">
            <label className="field">Anything else the agent should know?</label>
            <textarea value={base.notes} onChange={set("notes")} placeholder="Constraints, must-haves, companies to avoid…" />
          </div>
        </div>

        <div className="section-title" style={{ marginTop: 22 }}>
          <h3 style={{ margin: 0, fontSize: 13, textTransform: "uppercase", letterSpacing: ".6px", color: "var(--muted)" }}>
            Target roles &amp; resumes
          </h3>
        </div>
        <p className="note" style={{ marginTop: 0 }}>
          Add every role you want to apply for and attach a tailored resume for each. The agent applies
          to a role <b>only</b> when it has a matching resume.
        </p>

        {entries.map((en, i) => (
          <div key={i} className="form-grid" style={{ alignItems: "end", marginBottom: 10 }}>
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
                <button type="button" className="btn" style={{ background: "var(--chip)", color: "var(--ink)" }}
                  onClick={() => removeEntry(i)}>Remove</button>
              ) : null}
            </div>
          </div>
        ))}

        {entries.length < ROLES.length ? (
          <button type="button" className="btn" style={{ background: "var(--chip)", color: "var(--ink)" }} onClick={addEntry}>
            + Add another role
          </button>
        ) : null}

        <label className="consent" style={{ marginTop: 18 }}>
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          <span className="note">
            I give the Job Agent permission to search for jobs matching these roles and to prepare
            applications, using the matching resume for each role, for my review.
          </span>
        </label>

        {error ? <div className="error">{error}</div> : null}

        <div style={{ marginTop: 16 }}>
          <button className="btn" type="submit" disabled={busy}>
            {busy ? "Uploading…" : "Submit details & resumes"}
          </button>
        </div>
      </form>
    </>
  );
}
