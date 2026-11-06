"use client";

import { useMemo, useState } from "react";
import type { Application } from "@/lib/types";
import { Card, StatusPill, EmptyState } from "@/components/ui";

// Pipeline columns → which agent statuses fall into each.
const COLUMNS: { key: string; label: string; statuses: string[] }[] = [
  { key: "review", label: "Needs review", statuses: ["prepared", "awaiting_approval", "needs_human"] },
  { key: "approved", label: "Approved", statuses: ["approved"] },
  { key: "submitted", label: "Submitted", statuses: ["submitted", "submitted_unverified", "applied"] },
  { key: "interview", label: "Interview", statuses: ["interview"] },
  { key: "offer", label: "Offer", statuses: ["offer"] },
  { key: "closed", label: "Closed", statuses: ["rejected", "withdrawn", "failed", "no_response"] },
];

export default function ApplicationsBoard({ apps }: { apps: Application[] }) {
  const [view, setView] = useState<"board" | "table">("board");
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return apps;
    return apps.filter((a) =>
      `${a.title} ${a.company} ${a.platform ?? ""} ${a.status ?? ""}`.toLowerCase().includes(needle),
    );
  }, [apps, q]);

  const grouped = useMemo(() => {
    const map: Record<string, Application[]> = {};
    for (const col of COLUMNS) map[col.key] = [];
    const other: Application[] = [];
    for (const a of filtered) {
      const col = COLUMNS.find((c) => a.status && c.statuses.includes(a.status));
      if (col) map[col.key].push(a);
      else other.push(a);
    }
    return { map, other };
  }, [filtered]);

  return (
    <>
      <Card style={{ marginBottom: 16 }}>
        <div className="cluster" style={{ gap: 12 }}>
          <div style={{ flex: "1 1 240px", minWidth: 0 }}>
            <label className="sr-only" htmlFor="app-search">Search applications</label>
            <input
              id="app-search"
              type="search"
              placeholder="Search role, company, status…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <div className="segmented" role="group" aria-label="View">
            <button className={view === "board" ? "on" : ""} aria-pressed={view === "board"} onClick={() => setView("board")}>Board</button>
            <button className={view === "table" ? "on" : ""} aria-pressed={view === "table"} onClick={() => setView("table")}>Table</button>
          </div>
        </div>
        <p className="note mb-0" style={{ marginTop: 10 }}>
          Read-only view of the agent’s decisions. Approvals and status changes happen agent-side —
          this mirror never writes.
        </p>
      </Card>

      {filtered.length === 0 ? (
        <EmptyState icon="🗂️" title="No applications match your search" />
      ) : view === "board" ? (
        <div className="kanban">
          {COLUMNS.map((col) => (
            <div className="kanban-col" key={col.key}>
              <header>
                {col.label}
                <span className="count">{grouped.map[col.key].length}</span>
              </header>
              {grouped.map[col.key].length === 0 ? (
                <p className="faint" style={{ fontSize: 13, margin: "4px 2px" }}>—</p>
              ) : (
                grouped.map[col.key].map((a) => (
                  <div className="kanban-card" key={a.id}>
                    <p className="k-title">
                      {a.url ? (
                        <a href={a.url} target="_blank" rel="noopener noreferrer">{a.title}</a>
                      ) : (
                        a.title
                      )}
                    </p>
                    <p className="k-meta">@ {a.company}{a.platform ? ` · ${a.platform}` : ""}</p>
                    <div className="cluster" style={{ justifyContent: "space-between", marginTop: 9 }}>
                      <StatusPill status={a.status} />
                      <span className="score faint" title="Match score">{(a.score ?? 0).toFixed(0)}</span>
                    </div>
                    {a.selection_reason ? (
                      <p className="muted" style={{ fontSize: 12.5, margin: "8px 0 0" }}>{a.selection_reason}</p>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          ))}
        </div>
      ) : (
        <Card className="pad-0">
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Score</th><th>Role</th><th>Status</th><th>Resume</th><th>Why selected</th></tr>
              </thead>
              <tbody>
                {filtered.map((a) => (
                  <tr key={a.id}>
                    <td className="score">{(a.score ?? 0).toFixed(0)}</td>
                    <td>
                      {a.url ? (
                        <a href={a.url} target="_blank" rel="noopener noreferrer"><b>{a.title}</b></a>
                      ) : (
                        <b>{a.title}</b>
                      )}
                      <div className="muted">@ {a.company}{a.platform ? ` · ${a.platform}` : ""}</div>
                      {a.submitted_at ? (
                        <div className="faint" style={{ fontSize: 12 }}>
                          submitted {a.submitted_at.slice(0, 10)}
                          {a.verification ? ` · ${a.verification}` : ""}
                        </div>
                      ) : null}
                    </td>
                    <td><StatusPill status={a.status} /></td>
                    <td className="muted mono">{a.resume_version || "—"}</td>
                    <td className="muted" style={{ maxWidth: 360 }}>{a.selection_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}
