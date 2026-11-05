"use client";

import { useMemo, useState } from "react";
import type { Job } from "@/lib/types";
import { Card, Chip, StatusPill, EmptyState } from "@/components/ui";

function salary(j: Job): string {
  if (j.salary_min && j.salary_max)
    return `${(j.salary_min / 100000).toFixed(1)}–${(j.salary_max / 100000).toFixed(1)} LPA`;
  if (j.salary_max) return `up to ${(j.salary_max / 100000).toFixed(1)} LPA`;
  return "—";
}

type Sort = "score" | "recent";

export default function JobsExplorer({ jobs }: { jobs: Job[] }) {
  const [q, setQ] = useState("");
  const [family, setFamily] = useState<string>("all");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [sort, setSort] = useState<Sort>("score");
  const [view, setView] = useState<"table" | "cards">("table");

  const families = useMemo(
    () => Array.from(new Set(jobs.map((j) => j.role_family).filter(Boolean))).sort() as string[],
    [jobs],
  );

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let out = jobs.filter((j) => {
      if (family !== "all" && j.role_family !== family) return false;
      if (remoteOnly && !j.remote) return false;
      if (needle) {
        const hay = `${j.title} ${j.company} ${j.location ?? ""} ${j.platform ?? ""}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
    out = [...out].sort((a, b) =>
      sort === "score"
        ? (b.score ?? 0) - (a.score ?? 0)
        : (b.first_seen_at ?? "").localeCompare(a.first_seen_at ?? ""),
    );
    return out;
  }, [jobs, q, family, remoteOnly, sort]);

  return (
    <>
      {/* Toolbar */}
      <Card style={{ marginBottom: 16 }}>
        <div className="cluster" style={{ gap: 12 }}>
          <div style={{ flex: "1 1 240px", minWidth: 0 }}>
            <label className="sr-only" htmlFor="job-search">Search jobs</label>
            <input
              id="job-search"
              type="search"
              placeholder="Search title, company, location…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <div style={{ flex: "0 1 220px" }}>
            <label className="sr-only" htmlFor="job-family">Role family</label>
            <select id="job-family" value={family} onChange={(e) => setFamily(e.target.value)}>
              <option value="all">All role families</option>
              {families.map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </div>
          <label className="chip outline" style={{ cursor: "pointer", gap: 8, padding: "8px 12px" }}>
            <input
              type="checkbox"
              checked={remoteOnly}
              onChange={(e) => setRemoteOnly(e.target.checked)}
              style={{ width: "auto", accentColor: "var(--accent)" }}
            />
            Remote only
          </label>
          <div className="segmented" role="group" aria-label="Sort">
            <button className={sort === "score" ? "on" : ""} aria-pressed={sort === "score"} onClick={() => setSort("score")}>Top score</button>
            <button className={sort === "recent" ? "on" : ""} aria-pressed={sort === "recent"} onClick={() => setSort("recent")}>Newest</button>
          </div>
          <div className="segmented" role="group" aria-label="View">
            <button className={view === "table" ? "on" : ""} aria-pressed={view === "table"} onClick={() => setView("table")} aria-label="Table view">☰</button>
            <button className={view === "cards" ? "on" : ""} aria-pressed={view === "cards"} onClick={() => setView("cards")} aria-label="Card view">▦</button>
          </div>
        </div>
        <p className="note mb-0" style={{ marginTop: 10 }}>
          Showing <b>{filtered.length}</b> of {jobs.length} roles
        </p>
      </Card>

      {filtered.length === 0 ? (
        <EmptyState icon="🔎" title="No roles match your filters">
          Try clearing the search or role filter.
        </EmptyState>
      ) : view === "table" ? (
        <Card className="pad-0">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Score</th><th>Title</th><th>Company</th><th>Location</th>
                  <th>Platform</th><th>Salary</th><th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((j) => (
                  <tr key={j.id}>
                    <td className="score">{(j.score ?? 0).toFixed(1)}</td>
                    <td>
                      <b>{j.title}</b>
                      {j.role_family ? <div className="muted">{j.role_family}</div> : null}
                    </td>
                    <td>{j.company}</td>
                    <td>
                      {j.location || ""} {j.remote ? <Chip variant="accent">remote</Chip> : null}
                    </td>
                    <td>{j.platform ? <Chip variant="outline">{j.platform}</Chip> : "—"}</td>
                    <td className="muted nowrap">{salary(j)}</td>
                    <td className="muted" style={{ maxWidth: 320 }}>
                      {j.status ? <StatusPill status={j.status} /> : null}
                      {j.filter_reason
                        ? <div style={{ marginTop: 4 }}>{j.filter_reason}</div>
                        : j.missing && j.missing.length
                          ? <div style={{ marginTop: 4 }}>missing: {j.missing.slice(0, 3).join(", ")}</div>
                          : null}
                      {j.url ? (
                        <div style={{ marginTop: 4 }}>
                          <a href={j.url} target="_blank" rel="noopener noreferrer">posting ↗</a>
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <div className="grid cols-2">
          {filtered.map((j) => (
            <Card key={j.id} hover>
              <div className="cluster" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                <div style={{ minWidth: 0 }}>
                  <b style={{ fontSize: 15 }}>{j.title}</b>
                  <div className="muted">{j.company}{j.role_family ? ` · ${j.role_family}` : ""}</div>
                </div>
                <span className="chip accent score" title="Match score">{(j.score ?? 0).toFixed(1)}</span>
              </div>
              <div className="cluster" style={{ marginTop: 10, gap: 6 }}>
                {j.remote ? <Chip variant="accent">remote</Chip> : null}
                {j.location ? <Chip variant="outline">{j.location}</Chip> : null}
                {j.platform ? <Chip>{j.platform}</Chip> : null}
                <span className="chip">{salary(j)}</span>
              </div>
              {j.status ? <div style={{ marginTop: 10 }}><StatusPill status={j.status} /></div> : null}
              {(j.filter_reason || (j.missing && j.missing.length)) ? (
                <p className="muted" style={{ fontSize: 13, margin: "10px 0 0" }}>
                  {j.filter_reason || `missing: ${j.missing!.slice(0, 3).join(", ")}`}
                </p>
              ) : null}
              {j.url ? (
                <div style={{ marginTop: 12 }}>
                  <a className="btn ghost sm" href={j.url} target="_blank" rel="noopener noreferrer">View posting ↗</a>
                </div>
              ) : null}
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
