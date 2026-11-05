import { db } from "@/lib/supabase";
import type { Job } from "@/lib/types";

export const revalidate = 60;

function salary(j: Job): string {
  if (j.salary_min && j.salary_max) return `${(j.salary_min / 100000).toFixed(1)}–${(j.salary_max / 100000).toFixed(1)} LPA`;
  if (j.salary_max) return `up to ${(j.salary_max / 100000).toFixed(1)} LPA`;
  return "—";
}

export default async function JobsPage() {
  const supabase = await db();
  const { data: jobs, error } = await supabase
    .from("jobs")
    .select("*")
    .order("score", { ascending: false });

  if (error) return <div className="empty">Could not load jobs: {error.message}</div>;
  if (!jobs?.length) return <div className="empty">No jobs yet. Run the agent and sync to Supabase.</div>;

  return (
    <>
      <h2 className="section">
        Jobs<span className="sub">{jobs.length} discovered &amp; scored</span>
      </h2>
      <div className="card table">
        <table>
          <thead>
            <tr>
              <th>Score</th><th>Title</th><th>Company</th><th>Location</th>
              <th>Platform</th><th>Salary</th><th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {(jobs as Job[]).map((j) => (
              <tr key={j.id}>
                <td className="score">{(j.score ?? 0).toFixed(1)}</td>
                <td>
                  <b>{j.title}</b>
                  <div className="muted">{j.role_family}</div>
                </td>
                <td>{j.company}</td>
                <td>
                  {j.location || ""} {j.remote ? <span className="chip">remote</span> : null}
                </td>
                <td><span className="chip">{j.platform}</span></td>
                <td className="muted">{salary(j)}</td>
                <td className="muted">
                  {j.filter_reason
                    ? j.filter_reason
                    : j.missing && j.missing.length
                      ? `missing: ${j.missing.slice(0, 3).join(", ")}`
                      : ""}
                  {j.url ? (
                    <div>
                      <a href={j.url} target="_blank" rel="noopener noreferrer">posting ↗</a>
                    </div>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
