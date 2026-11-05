import { db } from "@/lib/supabase";
import type { Dashboard } from "@/lib/types";

export const revalidate = 60;

function StatusList({ rows }: { rows: { status: string; c: number }[] }) {
  if (!rows?.length) return <div className="muted">none yet</div>;
  return (
    <>
      {rows.map((r) => (
        <div className="row" key={r.status}>
          <span>{r.status}</span>
          <b>{r.c}</b>
        </div>
      ))}
    </>
  );
}

export default async function Page() {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) {
    return <div className="empty">Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY in .env.local.</div>;
  }

  const supabase = await db();
  const { data, error } = await supabase.from("stats").select("data,captured_at").eq("id", 1).maybeSingle();

  if (error || !data) {
    return (
      <div className="empty">
        No data yet. Run the agent locally and <code>python -m job_agent sync-supabase</code> to populate the showcase.
      </div>
    );
  }

  const d = data.data as Dashboard;
  return (
    <>
      <div className="grid">
        <div className="card">
          <h3>Submitted today</h3>
          <div className="big">{d.submitted_today}</div>
        </div>
        <div className="card">
          <h3>Applications by status</h3>
          <StatusList rows={d.apps_by_status} />
        </div>
        <div className="card">
          <h3>Jobs by status</h3>
          <StatusList rows={d.jobs_by_status} />
        </div>
        {d.unverified ? (
          <div className="card">
            <h3>Needs checking</h3>
            <div className="big" style={{ color: "var(--warn)" }}>{d.unverified}</div>
            <div className="muted">submitted without a confirmation page</div>
          </div>
        ) : null}
      </div>

      <h2 className="section">
        Waiting on you<span className="sub">prepared applications pending your approval</span>
      </h2>
      <div className="card">
        {d.waiting_on_you?.length ? (
          d.waiting_on_you.map((w) => (
            <div className="row" key={w.id}>
              <span>
                <b>{w.title}</b> <span className="muted">@ {w.company}</span>
                {w.selection_reason ? <div className="muted" style={{ fontSize: 13 }}>{w.selection_reason}</div> : null}
              </span>
              <span className={`st ${w.status}`}>{w.status}</span>
            </div>
          ))
        ) : (
          <div className="muted">Nothing waiting.</div>
        )}
      </div>

      <h2 className="section">
        What&apos;s working<span className="sub">interview rate by role family</span>
      </h2>
      <div className="card table">
        {d.performance?.length ? (
          <table>
            <thead>
              <tr>
                <th>Role family</th><th>Applied</th><th>Interviews</th><th>Rate</th><th>Avg score</th>
              </tr>
            </thead>
            <tbody>
              {d.performance.map((p) => (
                <tr key={p.family ?? "?"}>
                  <td>{p.family ?? "—"}</td>
                  <td>{p.applied}</td>
                  <td>{p.interviews ?? 0}</td>
                  <td>{p.interview_rate}%</td>
                  <td>{p.avg_score ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="muted" style={{ padding: 16 }}>No submitted applications yet.</div>
        )}
      </div>

      <h2 className="section">Follow-ups due</h2>
      <div className="card">
        {d.follow_ups?.length ? (
          d.follow_ups.map((f) => (
            <div className="row" key={f.id}>
              <span>{f.title} <span className="muted">@ {f.company}</span></span>
              <span className="chip">due {f.follow_up_on}</span>
            </div>
          ))
        ) : (
          <div className="muted">None due.</div>
        )}
      </div>
    </>
  );
}
