"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/utils/supabase/client";
import { Card, CardHead, PageHead, EmptyState, ErrorState, Skeleton } from "@/components/ui";

type Profile = {
  full_name: string; email: string; phone: string;
  preferred_locations: string; work_mode: string; experience_years: string;
  expected_salary: string; linkedin_url: string; portfolio_url: string;
  github_url: string; notes: string;
};
const EMPTY: Profile = {
  full_name: "", email: "", phone: "", preferred_locations: "", work_mode: "any",
  experience_years: "", expected_salary: "", linkedin_url: "", portfolio_url: "",
  github_url: "", notes: "",
};

export default function ProfilePage() {
  const [loading, setLoading] = useState(true);
  const [signedIn, setSignedIn] = useState(true);
  const [profileId, setProfileId] = useState<string | null>(null);
  const [consent, setConsent] = useState<boolean>(false);
  const [accountEmail, setAccountEmail] = useState<string | null>(null);
  const [form, setForm] = useState<Profile>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const supabase = createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) { setSignedIn(false); setLoading(false); return; }
    setAccountEmail(user.email ?? null);

    const { data, error } = await supabase
      .from("job_seekers")
      .select("id,full_name,email,phone,preferred_locations,work_mode,experience_years,expected_salary,linkedin_url,portfolio_url,github_url,notes,consent")
      .order("created_at", { ascending: false })
      .limit(1);
    if (error) { setError(error.message); setLoading(false); return; }

    const row = data?.[0];
    if (row) {
      setProfileId(row.id);
      setConsent(!!row.consent);
      setForm({
        full_name: row.full_name ?? "",
        email: row.email ?? user.email ?? "",
        phone: row.phone ?? "",
        preferred_locations: row.preferred_locations ?? "",
        work_mode: row.work_mode ?? "any",
        experience_years: row.experience_years != null ? String(row.experience_years) : "",
        expected_salary: row.expected_salary ?? "",
        linkedin_url: row.linkedin_url ?? "",
        portfolio_url: row.portfolio_url ?? "",
        github_url: row.github_url ?? "",
        notes: row.notes ?? "",
      });
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    try {
      if (localStorage.getItem("emc-theme") === "light") setTheme("light");
    } catch { /* ignore */ }
  }, []);

  const set = (k: keyof Profile) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  function applyTheme(next: "dark" | "light") {
    setTheme(next);
    if (next === "light") document.documentElement.setAttribute("data-theme", "light");
    else document.documentElement.removeAttribute("data-theme");
    try { localStorage.setItem("emc-theme", next); } catch { /* ignore */ }
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    if (!form.full_name.trim() || !form.email.trim()) { setError("Name and email are required."); return; }
    if (!profileId) { setError("No profile to update — complete onboarding first."); return; }

    setBusy(true);
    const supabase = createClient();
    const { error } = await supabase.from("job_seekers").update({
      full_name: form.full_name,
      email: form.email,
      phone: form.phone || null,
      preferred_locations: form.preferred_locations || null,
      work_mode: form.work_mode,
      experience_years: form.experience_years ? Number(form.experience_years) : null,
      expected_salary: form.expected_salary || null,
      linkedin_url: form.linkedin_url || null,
      portfolio_url: form.portfolio_url || null,
      github_url: form.github_url || null,
      notes: form.notes || null,
    }).eq("id", profileId);
    setBusy(false);
    if (error) { setError(error.message); return; }
    setNotice("Profile saved.");
  }

  if (!signedIn) {
    return (
      <>
        <PageHead title="Profile & Preferences" />
        <ErrorState title="Please sign in"><Link href="/login">Sign in</Link> to manage your profile.</ErrorState>
      </>
    );
  }

  return (
    <>
      <PageHead title="Profile & Preferences" subtitle="Your details, the roles you target, and app preferences." />

      {error ? <div className="error" style={{ marginBottom: 14 }}>{error}</div> : null}
      {notice ? <div className="note" style={{ color: "var(--good)", marginBottom: 14 }}>{notice}</div> : null}

      {loading ? (
        <Card><Skeleton className="sk-line w-40" /><Skeleton className="sk-line w-80" /><Skeleton className="sk-line w-60" /></Card>
      ) : !profileId ? (
        <EmptyState icon="👤" title="No profile yet" action={<Link className="btn" href="/get-started">Complete onboarding →</Link>}>
          Set up your job hunt to create your profile.
        </EmptyState>
      ) : (
        <div className="stack">
          {/* Account */}
          <Card>
            <CardHead title="Account" />
            <div className="row"><span className="muted">Signed in as</span><b>{accountEmail || "—"}</b></div>
            <div className="row">
              <span className="muted">Agent consent</span>
              <span className={consent ? "pill good" : "pill warn"}>{consent ? "granted" : "not granted"}</span>
            </div>
            <p className="note mb-0" style={{ marginTop: 10 }}>
              Account email is managed by sign-in. {consent ? "The agent is authorised to prepare applications for your review." : "Re-submit onboarding to authorise the agent."}
            </p>
          </Card>

          {/* Preferences */}
          <Card>
            <CardHead title="Preferences" />
            <div className="row">
              <span className="muted">Theme</span>
              <div className="segmented" role="group" aria-label="Theme">
                <button className={theme === "dark" ? "on" : ""} aria-pressed={theme === "dark"} onClick={() => applyTheme("dark")}>Dark</button>
                <button className={theme === "light" ? "on" : ""} aria-pressed={theme === "light"} onClick={() => applyTheme("light")}>Light</button>
              </div>
            </div>
            <div className="row">
              <span className="muted">Resumes</span>
              <Link className="btn ghost sm" href="/resume-studio">Manage in Resume Studio →</Link>
            </div>
          </Card>

          {/* Editable profile */}
          <form onSubmit={save}>
            <Card>
              <CardHead title="Your details" />
              <div className="form-grid">
                <div>
                  <label className="field" htmlFor="full_name">Full name <span className="req">*</span></label>
                  <input id="full_name" value={form.full_name} onChange={set("full_name")} required />
                </div>
                <div>
                  <label className="field" htmlFor="email">Email <span className="req">*</span></label>
                  <input id="email" type="email" value={form.email} onChange={set("email")} required />
                </div>
                <div>
                  <label className="field" htmlFor="phone">Phone</label>
                  <input id="phone" value={form.phone} onChange={set("phone")} />
                </div>
                <div>
                  <label className="field" htmlFor="locs">Preferred locations</label>
                  <input id="locs" value={form.preferred_locations} onChange={set("preferred_locations")} placeholder="e.g. Bengaluru, Remote" />
                </div>
                <div>
                  <label className="field" htmlFor="work_mode">Work mode</label>
                  <select id="work_mode" value={form.work_mode} onChange={set("work_mode")}>
                    <option value="any">Any</option>
                    <option value="remote">Remote</option>
                    <option value="hybrid">Hybrid</option>
                    <option value="onsite">Onsite</option>
                  </select>
                </div>
                <div>
                  <label className="field" htmlFor="exp">Years of experience</label>
                  <input id="exp" type="number" min="0" step="0.5" value={form.experience_years} onChange={set("experience_years")} />
                </div>
                <div>
                  <label className="field" htmlFor="sal">Expected salary</label>
                  <input id="sal" value={form.expected_salary} onChange={set("expected_salary")} placeholder="e.g. 12 LPA" />
                </div>
                <div>
                  <label className="field" htmlFor="li">LinkedIn URL</label>
                  <input id="li" value={form.linkedin_url} onChange={set("linkedin_url")} placeholder="https://linkedin.com/in/…" />
                </div>
                <div>
                  <label className="field" htmlFor="pf">Portfolio URL</label>
                  <input id="pf" value={form.portfolio_url} onChange={set("portfolio_url")} />
                </div>
                <div>
                  <label className="field" htmlFor="gh">GitHub URL</label>
                  <input id="gh" value={form.github_url} onChange={set("github_url")} />
                </div>
                <div className="field-full">
                  <label className="field" htmlFor="notes">Notes for the agent</label>
                  <textarea id="notes" value={form.notes} onChange={set("notes")} placeholder="Constraints, must-haves, companies to avoid…" />
                </div>
              </div>
              <div style={{ marginTop: 16 }}>
                <button className="btn" type="submit" disabled={busy}>{busy ? "Saving…" : "Save changes"}</button>
              </div>
            </Card>
          </form>
        </div>
      )}
    </>
  );
}
