import { db } from "@/lib/supabase";
import type { Application } from "@/lib/types";

export const revalidate = 60;

export default async function ApplicationsPage() {
  const supabase = await db();
  const { data: apps, error } = await supabase
    .from("applications")
    .select("*")
    .order("score", { ascending: false });

  if (error) return <div className="empty">Could not load applications: {error.message}</div>;
  if (!apps?.length) return <div className="empty">No applications yet.</div>;

  return (
    <>
      <h2 className="section">
        Applications<span className="sub">every decision the agent made, with its reasoning</span>
      </h2>
      <div className="card table">
        <table>
          <thead>
            <tr>
              <th>Score</th><th>Role</th><th>Status</th><th>Resume</th><th>Why selected</th>
            </tr>
          </thead>
          <tbody>
            {(apps as Application[]).map((a) => (
              <tr key={a.id}>
                <td className="score">{(a.score ?? 0).toFixed(0)}</td>
                <td>
                  {a.url ? (
                    <a href={a.url} target="_blank" rel="noopener noreferrer"><b>{a.title}</b></a>
                  ) : (
                    <b>{a.title}</b>
                  )}
                  <div className="muted">@ {a.company} · {a.platform}</div>
                  {a.submitted_at ? (
                    <div className="muted" style={{ fontSize: 12 }}>
                      submitted {a.submitted_at.slice(0, 10)}
                      {a.verification ? ` · ${a.verification}` : ""}
                    </div>
                  ) : null}
                </td>
                <td><span className={`st ${a.status}`}>{a.status}</span></td>
                <td className="muted">{a.resume_version || "—"}</td>
                <td className="muted">{a.selection_reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
