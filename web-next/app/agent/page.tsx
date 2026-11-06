import Link from "next/link";
import { db } from "@/lib/supabase";
import type { Dashboard } from "@/lib/types";
import { labelForRole, parseRoles } from "@/lib/roles";
import { SUBMITTED_LIKE } from "@/lib/status";
import { Card, CardHead, PageHead, Stat, StatusPill, EmptyState, ErrorState } from "@/components/ui";

export const revalidate = 60;

const sum = (rows: { status: string; c: number }[], statuses: readonly string[]) =>
  rows.filter((r) => statuses.includes(r.status)).reduce((n, r) => n + r.c, 0);

type FunnelStage = { label: string; value: number };

export default async function AgentControlCenter() {
  const supabase = await db();

  // Public mirror snapshot.
  const { data: statsRow, error: statsErr } = await supabase
    .from("stats")
    .select("data,captured_at")
    .eq("id", 1)
    .maybeSingle();

  // Current user's own readiness (owner-scoped RLS via the session cookie).
  const [seekersRes, resumesRes] = await Promise.all([
    supabase.from("job_seekers").select("id,target_roles,created_at,consent").order("created_at", { ascending: false }),
    supabase.from("resumes").select("seeker_id,target_role"),
  ]);
  const readinessError = seekersRes.error?.message ?? resumesRes.error?.message ?? null;

  const profile = seekersRes.data?.[0] ?? null;
  const targetRoles = parseRoles(profile?.target_roles);
  // Scope resume coverage to THIS profile only — the agent checks resumes by
  // seeker_id, so coverage counted across older profiles would overstate it.
  const coveredRoles = new Set(
    (resumesRes.data ?? []).filter((r) => profile && r.seeker_id === profile.id).map((r) => r.target_role),
  );
  const missingRoles = targetRoles.filter((r) => !coveredRoles.has(r));
  // READY must also carry consent — the agent only processes consented seekers.
  const ready = targetRoles.length > 0 && missingRoles.length === 0 && !!profile?.consent;

  const capturedAt = statsRow?.captured_at
    ? new Date(statsRow.captured_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : null;

  // Pipeline funnel (honest counts from the mirror; applications progress downward).
  let funnel: FunnelStage[] = [];
  let waiting: Dashboard["waiting_on_you"] = [];
  let submittedToday = 0;
  let unverified = 0;
  if (statsRow?.data) {
    const s = statsRow.data as Dashboard;
    waiting = s.waiting_on_you ?? [];
    submittedToday = s.submitted_today ?? 0;
    unverified = s.unverified ?? 0;
    const jobsDiscovered = s.jobs_by_status.reduce((n, r) => n + r.c, 0);
    const prepared = sum(s.apps_by_status, ["prepared", "awaiting_approval", "needs_human", "approved", ...SUBMITTED_LIKE]);
    const awaiting = sum(s.apps_by_status, ["prepared", "awaiting_approval", "needs_human"]);
    const submitted = sum(s.apps_by_status, SUBMITTED_LIKE);
    const interview = sum(s.apps_by_status, ["interview"]);
    const offer = sum(s.apps_by_status, ["offer"]);
    funnel = [
      { label: "Jobs discovered", value: jobsDiscovered },
      { label: "Applications prepared", value: prepared },
      { label: "Awaiting your approval", value: awaiting },
      { label: "Submitted", value: submitted },
      { label: "Interview", value: interview },
      { label: "Offer", value: offer },
    ];
  }
  const funnelTop = Math.max(1, ...funnel.map((f) => f.value));

  return (
    <>
      <PageHead
        title="AI Agent Control Center"
        subtitle="Monitor the agent’s pipeline and act on what it’s waiting on you for."
        actions={<Link className="btn ghost sm" href="/applications">Review applications</Link>}
      />

      {/* Honest capability banner — read panel, not a live control plane */}
      <Card accent style={{ marginBottom: 20 }}>
        <div className="cluster" style={{ gap: 12, alignItems: "flex-start" }}>
          <div className="ic" aria-hidden style={{ width: 40, height: 40, borderRadius: 11, display: "grid", placeItems: "center", background: "var(--accent-soft)", color: "var(--accent)", border: "1px solid var(--accent-line)", fontSize: 19, flex: "none" }}>⚙</div>
          <div>
            <h3 style={{ color: "var(--ink)", fontSize: 15, textTransform: "none", letterSpacing: "-0.01em", margin: "0 0 4px" }}>
              This is a control panel, not a control plane
            </h3>
            <p className="muted mb-0" style={{ maxWidth: "70ch" }}>
              The agent runs locally — its SQLite database is the source of truth. This page reflects a
              privacy-filtered mirror of that activity and holds your approvals. It <b>cannot start, stop,
              or steer a live run</b>; execution happens agent-side, and nothing is ever submitted without
              your approval.
            </p>
          </div>
        </div>
      </Card>

      {/* Readiness gate (your own data) */}
      <h2 className="section">Your readiness<span className="sub">the agent only applies to a role once it has a matching resume</span></h2>
      <Card>
        {readinessError ? (
          <div className="error" role="alert" style={{ marginBottom: 12 }}>
            Couldn’t load your profile or resumes ({readinessError}). Readiness below may be inaccurate.
          </div>
        ) : null}
        {!profile ? (
          <EmptyState
            icon="🚦"
            title="No profile yet"
            action={<Link className="btn" href="/get-started">Set up your job hunt →</Link>}
          >
            Add your target roles and a resume for each to become READY.
          </EmptyState>
        ) : (
          <>
            <div className="cluster" style={{ justifyContent: "space-between" }}>
              <div className="cluster" style={{ gap: 10 }}>
                <span className={ready ? "pill good" : "pill warn"} style={{ fontSize: 13 }}>
                  {ready ? "READY" : "BLOCKED"}
                </span>
                <span className="muted">
                  {ready
                    ? "every targeted role has a resume and consent is recorded — the agent can apply for you"
                    : missingRoles.length > 0
                      ? `${missingRoles.length} role${missingRoles.length === 1 ? "" : "s"} still need a resume`
                      : !profile.consent
                        ? "consent isn’t recorded — re-submit onboarding to authorise the agent"
                        : "add at least one target role to get started"}
                </span>
              </div>
              {!ready && missingRoles.length > 0 ? <Link className="btn sm" href="/resume-studio">Add resumes →</Link> : null}
            </div>
            <div className="cluster" style={{ marginTop: 14 }}>
              {targetRoles.length === 0 ? (
                <span className="muted">No target roles yet.</span>
              ) : (
                targetRoles.map((r) => (
                  <span key={r} className={coveredRoles.has(r) ? "pill good" : "pill warn"}>
                    {labelForRole(r)}{coveredRoles.has(r) ? "" : " · needs resume"}
                  </span>
                ))
              )}
            </div>
            {!profile.consent ? (
              <p className="note" style={{ marginTop: 12 }}>
                ⚠ Consent isn’t recorded on your latest profile — re-submit the wizard to authorise the agent.
              </p>
            ) : null}
          </>
        )}
      </Card>

      {/* Pipeline + queue */}
      {statsErr ? (
        <ErrorState title="Couldn’t load agent activity">{statsErr.message}</ErrorState>
      ) : !statsRow ? (
        <>
          <h2 className="section">Pipeline</h2>
          <EmptyState icon="📡" title="No agent activity yet">
            Run the agent and <code className="mono">python -m job_agent sync-supabase</code> to see its pipeline here.
          </EmptyState>
        </>
      ) : (
        <>
          <div className="grid" style={{ marginTop: 22 }}>
            <Card hover><Stat label="Submitted today" value={submittedToday} /></Card>
            <Card hover><Stat label="Awaiting your approval" value={waiting.length} foot={waiting.length ? "needs a decision" : "all caught up"} /></Card>
            <Card hover accent={unverified > 0}><Stat label="Needs checking" value={<span style={{ color: unverified ? "var(--warn)" : undefined }}>{unverified}</span>} foot="no confirmation page" /></Card>
          </div>

          <h2 className="section">Pipeline<span className="sub">how work flows through the agent</span></h2>
          <Card>
            <div className="funnel">
              {funnel.map((f, i) => {
                const pct = Math.max(8, (f.value / funnelTop) * 100);
                const prev = i > 0 ? funnel[i - 1] : null;
                const conv = prev && prev.value ? Math.round((f.value / prev.value) * 100) : null;
                return (
                  <div className="funnel-stage" key={f.label}>
                    <div className="funnel-bar" style={{ width: `${pct}%` }}>
                      <span className="n">{f.value}</span>
                      <span className="lbl">{f.label}</span>
                    </div>
                    {conv !== null ? <span className="conv">{conv}% of previous</span> : null}
                  </div>
                );
              })}
            </div>
          </Card>

          <h2 className="section">Waiting on you<span className="sub">prepared applications pending your approval</span></h2>
          <Card className="pad-0">
            {waiting.length ? (
              <div style={{ padding: "6px 18px" }}>
                {waiting.map((w) => (
                  <div className="row" key={w.id}>
                    <span style={{ minWidth: 0 }}>
                      <b>{w.title}</b> <span className="muted">@ {w.company}</span>
                      {w.selection_reason ? <div className="muted" style={{ fontSize: 13 }}>{w.selection_reason}</div> : null}
                    </span>
                    <StatusPill status={w.status} />
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ padding: 18 }}><span className="muted">Nothing waiting — you’re all caught up. 🎉</span></div>
            )}
          </Card>
        </>
      )}

      {/* How execution works — honest, read-only */}
      <h2 className="section">How runs are triggered<span className="sub">execution is agent-side (CLI), by design</span></h2>
      <Card>
        <CardHead title="Agent commands" />
        <p className="muted mt-0">
          These run on the machine hosting the agent. The web app never executes them — it reads the
          results the agent syncs back.
        </p>
        <div className="stack" style={{ gap: 8 }}>
          {[
            ["python -m job_agent seekers", "List consented users and READY / BLOCKED status"],
            ["python -m job_agent discover", "Find new roles across sources"],
            ["python -m job_agent score", "Score & shortlist roles that fit"],
            ["python -m job_agent prepare", "Prepare applications for review"],
            ["python -m job_agent sync-supabase", "Push the privacy-filtered mirror to this app"],
          ].map(([cmd, desc]) => (
            <div className="row" key={cmd}>
              <code className="mono">{cmd}</code>
              <span className="muted" style={{ fontSize: 13, textAlign: "right" }}>{desc}</span>
            </div>
          ))}
        </div>
      </Card>

      {capturedAt ? <p className="note center" style={{ marginTop: 24 }}>Mirror last synced {capturedAt}</p> : null}
    </>
  );
}
