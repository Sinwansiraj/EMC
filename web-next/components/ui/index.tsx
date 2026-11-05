/** EMC reusable UI primitives — presentational, server-component-safe (no hooks,
 *  no browser APIs). Styling comes from the design tokens in app/globals.css. */
import * as React from "react";
import { toneFor, labelFor, type Tone } from "@/lib/status";

type Div = React.HTMLAttributes<HTMLDivElement>;

/* ------------------------------------------------------------------- Card --- */
export function Card({
  className = "",
  hover = false,
  accent = false,
  children,
  ...rest
}: Div & { hover?: boolean; accent?: boolean }) {
  const cls = ["card", hover ? "hover" : "", accent ? "accent" : "", className]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={cls} {...rest}>
      {children}
    </div>
  );
}

export function CardHead({
  title,
  action,
}: {
  title: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="card-head">
      <h3>{title}</h3>
      {action ? <span className="spacer">{action}</span> : null}
    </div>
  );
}

/* --------------------------------------------------------------- PageHead --- */
export function PageHead({
  title,
  subtitle,
  actions,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="page-head">
      <div className="titles">
        <h1>{title}</h1>
        {subtitle ? <p className="lede-sm mb-0">{subtitle}</p> : null}
      </div>
      {actions ? <div className="actions">{actions}</div> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ Badge --- */
export function Chip({
  children,
  variant,
  className = "",
}: {
  children: React.ReactNode;
  variant?: "outline" | "accent";
  className?: string;
}) {
  return <span className={`chip ${variant ?? ""} ${className}`.trim()}>{children}</span>;
}

/** Status pill that colours itself from the agent status taxonomy. */
export function StatusPill({ status, className = "" }: { status?: string | null; className?: string }) {
  const tone = toneFor(status);
  return <span className={`pill ${tone} ${className}`.trim()}>{labelFor(status)}</span>;
}

export function Pill({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return <span className={`pill ${tone}`}>{children}</span>;
}

/* ------------------------------------------------------------------- Stat --- */
export function Stat({
  label,
  value,
  foot,
  trend,
}: {
  label: React.ReactNode;
  value: React.ReactNode;
  foot?: React.ReactNode;
  trend?: { dir: "up" | "down" | "flat"; text: string };
}) {
  return (
    <div className="stat">
      <span className="label">{label}</span>
      <span className="val">{value}</span>
      {trend ? <span className={`trend ${trend.dir}`}>{trend.text}</span> : null}
      {foot ? <span className="foot">{foot}</span> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ Meter --- */
export function Meter({ value, max = 100, tone }: { value: number; max?: number; tone?: "good" | "warn" }) {
  const pct = Math.max(0, Math.min(100, max ? (value / max) * 100 : 0));
  return (
    <div className={`meter ${tone ?? ""}`.trim()} role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
      <span style={{ width: `${pct}%` }} />
    </div>
  );
}

/* --------------------------------------------------------------- BarChart --- */
export type Bar = { label: React.ReactNode; value: number; display?: string; tone?: "good" | "warn" | "bad" };

/** Horizontal single-hue magnitude bars. Identity is carried by the label,
 *  never by colour; tone is reserved for status and always shows its number. */
export function BarChart({ data, max, unit = "", size }: { data: Bar[]; max?: number; unit?: string; size?: "sm" }) {
  const top = max ?? Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="bars" role="img" aria-label="bar chart">
      {data.map((d, i) => {
        const pct = Math.max(0, Math.min(100, (d.value / top) * 100));
        return (
          <div className={`bar-row ${size ?? ""}`.trim()} key={i}>
            <span className="bar-label" title={typeof d.label === "string" ? d.label : undefined}>{d.label}</span>
            <span className="bar-track">
              <span className={`bar-fill ${d.tone ?? ""}`.trim()} style={{ width: `${pct}%` }} />
            </span>
            <span className="bar-val">{d.display ?? `${d.value}${unit}`}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ----------------------------------------------------------------- States --- */
export function EmptyState({
  icon = "✨",
  title,
  children,
  action,
}: {
  icon?: React.ReactNode;
  title: React.ReactNode;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <div className="icon" aria-hidden>{icon}</div>
      <h3>{title}</h3>
      {children ? <div className="note">{children}</div> : null}
      {action ? <div style={{ marginTop: 16 }}>{action}</div> : null}
    </div>
  );
}

export function ErrorState({ title = "Something went wrong", children }: { title?: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="error-state" role="alert">
      <div className="icon" aria-hidden>!</div>
      <h3 style={{ color: "var(--ink)", margin: "0 0 6px" }}>{title}</h3>
      {children ? <div className="note">{children}</div> : null}
    </div>
  );
}

export function Skeleton({ className = "", style }: { className?: string; style?: React.CSSProperties }) {
  return <div className={`skeleton ${className}`.trim()} style={style} aria-hidden />;
}

export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <Card className="pad-0">
      <div style={{ padding: 16 }}>
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} style={{ display: "flex", gap: 16, padding: "10px 0" }}>
            {Array.from({ length: cols }).map((_, c) => (
              <Skeleton key={c} className="sk-line" style={{ flex: c === 1 ? 2 : 1 }} />
            ))}
          </div>
        ))}
      </div>
    </Card>
  );
}
