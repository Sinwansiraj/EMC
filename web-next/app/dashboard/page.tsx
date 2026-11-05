import Link from "next/link";
import { db } from "@/lib/supabase";
import type { Dashboard } from "@/lib/types";
import {
  Card,
  CardHead,
  PageHead,
  Stat,
  StatusPill,
  Meter,
  EmptyState,
  ErrorState,
} from "@/components/ui";

export const revalidate = 60;

const sum = (rows: { status: string; c: number }[], statuses: string[]) =>
  rows.filter((r) => statuses.includes(r.status)).reduce((n, r) => n + r.c, 0);

function StatusList({ rows }: { rows: { status: string; c: number }[] }) {
  if (!rows?.length) return <div className="muted">none yet</div>;
  return (
    <>
      {rows.map((r) => (
        <div className="row" key={r.status}>
          <StatusPill status={r.status} />
          <b className="score">{r.c}</b>
        </div>
      ))}
    </>
  );
}

export default async function Page() {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) {
    return (
      <ErrorState title="Supabase is not configured">
        Set <code className="mono">NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
        <code className="mono">NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY</code> in <code className="mono">.env.local</code>.
      </ErrorState>
    );
  }

  const supabase = await db();
  const { data, error } = await supabase
    .from("stats")
    .select("data,captured_at")
    .eq("id", 1)
    .maybeSingle();

  if (error) {
    return (
      <ErrorState title="Couldn’t load your dashboard">{error.message}</ErrorState>
    );
  }

  if (!data) {
    return (
      <>
        <PageHead title="Dashboard" subtitle="Your live job-hunt activity, mirrored from the agent." />
        <EmptyState
          icon="📊"
          title="No activity yet"
          action={<Link className="btn" href="/get-started">Set up your job hunt →</Link>}
        >
          Run the agent and <code className="mono">python -m job_agent sync-supabase</code> to populate the dashboard.
        </EmptyState>
      </>
    );
  }

  const d = data.data as Dashboard;
  const capturedAt = data.captured_at
    ? new Date(data.captured_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : null;

  // Derived KPIs — all computed from the read-model, never hardcoded.
  const totalApps = d.apps_by_status.reduce((n, r) => n + r.c, 0);
  const submittedLike = sum(d.apps_by_status, ["submitted", "submitted_unverified", "applied", "interview", "offer"]);
  const interviews = sum(d.apps_by_status, ["interview"]);
  const offers = sum(d.apps_by_status, ["offer"]);
  const waiting = d.waiting_on_you?.length ?? 0;
  const interviewRate = submittedLike ? Math.round((interviews / submittedLike) * 100) : 0;

  return (
    <>
      <PageHead
        title="Dashboard"
        subtitle="Your live job-hunt activity, mirrored from the agent. Nothing is submitted without your approval."
        actions={
          <>
            <Link className="btn ghost sm" href="/jobs">View jobs</Link>
            <Link className="btn sm" href="/applications">Review applications</Link>
          </>
        }
      />

      {/* KPI row */}
      <div className="grid">
        <Card hover><Stat label="Submitted today" value={d.submitted_today} foot={`${submittedLike} submitted all-time`} /></Card>
        <Card hover><Stat label="Awaiting your approval" value={waiting} foot={waiting ? "needs a human decision" : "you’re all caught up"} /></Card>
        <Card hover><Stat label="Interviews" value={interviews} trend={submittedLike ? { dir: interviewRate >= 10 ? "up" : "flat", text: `${interviewRate}% of submitted` } : undefined} /></Card>
        <Card hover><Stat label="Offers" value={offers} foot={`${totalApps} applications tracked`} /></Card>
        {d.unverified ? (
          <Card hover accent>
            <Stat
              label="Needs checking"
              value={<span style={{ color: "var(--warn)" }}>{d.unverified}</span>}
              foot="submitted without a confirmation page"
            />
          </Card>
        ) : null}
      </div>

      {/* Approval queue — human-in-the-loop front and centre */}
      <h2 className="section">
        Waiting on you<span className="sub">prepared applications pending your approval</span>
      </h2>
      <Card className="pad-0">
        {d.waiting_on_you?.length ? (
          <div style={{ padding: "6px 18px" }}>
            {d.waiting_on_you.map((w) => (
              <div className="row" key={w.id}>
                <span style={{ minWidth: 0 }}>
                  <b>{w.title}</b> <span className="muted">@ {w.company}</span>
                  {w.selection_reason ? (
                    <div className="muted" style={{ fontSize: 13 }}>{w.selection_reason}</div>
                  ) : null}
                </span>
                <StatusPill status={w.status} />
              </div>
            ))}
          </div>
        ) : (
          <div style={{ padding: 18 }}>
            <span className="muted">Nothing waiting — every prepared application has been reviewed. 🎉</span>
          </div>
        )}
      </Card>

      {/* Two-column: performance + pipeline */}
      <div className="grid cols-2" style={{ marginTop: 22, alignItems: "start" }}>
        <Card className="pad-0">
          <div style={{ padding: "16px 18px 4px" }}>
            <CardHead title="What’s working" action={<span className="sub" style={{ margin: 0 }}>interview rate by role family</span>} />
          </div>
          {d.performance?.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Role family</th><th>Applied</th><th>Interviews</th><th>Rate</th><th>Avg score</th></tr>
                </thead>
                <tbody>
                  {d.performance.map((p) => (
                    <tr key={p.family ?? "?"}>
                      <td><b>{p.family ?? "—"}</b></td>
                      <td className="score">{p.applied}</td>
                      <td className="score">{p.interviews ?? 0}</td>
                      <td style={{ minWidth: 120 }}>
                        <div className="cluster" style={{ gap: 8, flexWrap: "nowrap" }}>
                          <b className="score" style={{ width: 38 }}>{p.interview_rate}%</b>
                          <Meter value={p.interview_rate} tone={p.interview_rate >= 15 ? "good" : undefined} />
                        </div>
                      </td>
                      <td className="score">{p.avg_score ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="muted" style={{ padding: 18 }}>No submitted applications yet.</div>
          )}
        </Card>

        <div className="stack">
          <Card>
            <CardHead title="Pipeline by source" />
            {d.by_source?.length ? (
              d.by_source.map((s) => (
                <div className="row" key={s.source}>
                  <span className="chip outline">{s.source || "—"}</span>
                  <span className="cluster" style={{ gap: 14 }}>
                    <span className="muted">{s.applied} applied</span>
                    <b className="score">{s.interviews} int.</b>
                  </span>
                </div>
              ))
            ) : (
              <div className="muted">No submitted applications yet.</div>
            )}
          </Card>

          <Card>
            <CardHead title="Jobs by status" />
            <StatusList rows={d.jobs_by_status} />
          </Card>
        </div>
      </div>

      {/* Follow-ups */}
      <h2 className="section">Follow-ups due</h2>
      <Card className="pad-0">
        {d.follow_ups?.length ? (
          <div style={{ padding: "6px 18px" }}>
            {d.follow_ups.map((f) => (
              <div className="row" key={f.id}>
                <span>{f.title} <span className="muted">@ {f.company}</span></span>
                <span className="chip">due {f.follow_up_on}</span>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ padding: 18 }}><span className="muted">None due.</span></div>
        )}
      </Card>

      {capturedAt ? (
        <p className="note center" style={{ marginTop: 24 }}>Last synced {capturedAt}</p>
      ) : null}
    </>
  );
}
