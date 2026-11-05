import Link from "next/link";
import { db } from "@/lib/supabase";
import type { Job, Dashboard } from "@/lib/types";
import { Card, CardHead, PageHead, Stat, BarChart, EmptyState, ErrorState, type Bar } from "@/components/ui";

export const revalidate = 60;

const median = (xs: number[]) => {
  if (!xs.length) return 0;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

const countBy = <T,>(items: T[], key: (x: T) => string | null | undefined) => {
  const m = new Map<string, number>();
  for (const it of items) {
    const k = key(it);
    if (!k) continue;
    m.set(k, (m.get(k) ?? 0) + 1);
  }
  return m;
};

const sum = (rows: { status: string; c: number }[], statuses: string[]) =>
  rows.filter((r) => statuses.includes(r.status)).reduce((n, r) => n + r.c, 0);

export default async function CareerIntelligence() {
  const supabase = await db();
  const [jobsRes, statsRes] = await Promise.all([
    supabase.from("jobs").select("*"),
    supabase.from("stats").select("data").eq("id", 1).maybeSingle(),
  ]);

  if (jobsRes.error) {
    return (
      <>
        <PageHead title="Career Intelligence" />
        <ErrorState title="Couldn’t load analytics">{jobsRes.error.message}</ErrorState>
      </>
    );
  }

  const jobs = (jobsRes.data as Job[]) ?? [];
  const stats = (statsRes.data?.data as Dashboard) ?? null;

  if (!jobs.length) {
    return (
      <>
        <PageHead title="Career Intelligence" subtitle="Insights derived from the roles the agent has analysed." />
        <EmptyState
          icon="📈"
          title="Not enough data yet"
          action={<Link className="btn" href="/get-started">Set up your job hunt →</Link>}
        >
          Once the agent discovers and scores roles, this page turns them into insights.
        </EmptyState>
      </>
    );
  }

  // --- KPIs (all derived) ---
  const scores = jobs.map((j) => j.score ?? 0).filter((s) => s > 0);
  const medianScore = median(scores);
  const submittedLike = stats ? sum(stats.apps_by_status, ["submitted", "submitted_unverified", "applied", "interview", "offer"]) : 0;
  const interviews = stats ? sum(stats.apps_by_status, ["interview"]) : 0;
  const overallRate = submittedLike ? Math.round((interviews / submittedLike) * 100) : 0;

  // --- interview rate by family (from the mirror performance block) ---
  const perfBars: Bar[] = (stats?.performance ?? [])
    .filter((p) => p.applied > 0)
    .map((p) => ({ label: p.family ?? "—", value: p.interview_rate, display: `${p.interview_rate}%`, tone: p.interview_rate >= 15 ? "good" : undefined }));

  // --- applications by source ---
  const sourceBars: Bar[] = (stats?.by_source ?? []).map((s) => ({
    label: s.source || "—",
    value: s.applied,
    display: s.interviews ? `${s.applied} · ${s.interviews} int` : `${s.applied}`,
  }));

  // --- match-score distribution (buckets of 20) ---
  const buckets = [0, 0, 0, 0, 0]; // 0-20,20-40,40-60,60-80,80-100
  for (const s of scores) buckets[Math.min(4, Math.floor(s / 20))]++;
  const scoreBars: Bar[] = buckets.map((c, i) => ({ label: `${i * 20}–${i * 20 + 20}`, value: c }));

  // --- role-family mix ---
  const familyBars: Bar[] = Array.from(countBy(jobs, (j) => j.role_family).entries())
    .sort((a, b) => b[1] - a[1])
    .map(([label, value]) => ({ label, value }));

  // --- top companies ---
  const companyBars: Bar[] = Array.from(countBy(jobs, (j) => j.company).entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([label, value]) => ({ label, value }));

  // --- salary insight (LPA from salary_max) ---
  const salaried = jobs.map((j) => j.salary_max).filter((x): x is number => !!x).map((x) => x / 100000);
  const salLow = salaried.length ? Math.min(...salaried) : 0;
  const salMed = median(salaried);
  const salHigh = salaried.length ? Math.max(...salaried) : 0;

  // --- remote split ---
  const remote = jobs.filter((j) => j.remote).length;
  const remoteBars: Bar[] = [
    { label: "Remote", value: remote },
    { label: "On-site / Hybrid", value: jobs.length - remote },
  ];

  return (
    <>
      <PageHead
        title="Career Intelligence"
        subtitle="Insights derived from the roles the agent has discovered, scored, and applied to."
      />

      {/* KPI hero tiles */}
      <div className="grid">
        <Card hover><Stat label="Roles analysed" value={jobs.length} foot={`${scores.length} scored`} /></Card>
        <Card hover><Stat label="Median match score" value={medianScore.toFixed(1)} foot="across scored roles" /></Card>
        <Card hover><Stat label="Applications submitted" value={submittedLike} /></Card>
        <Card hover><Stat label="Interview rate" value={`${overallRate}%`} trend={submittedLike ? { dir: overallRate >= 10 ? "up" : "flat", text: `${interviews} interviews` } : undefined} /></Card>
      </div>

      <div className="grid cols-2" style={{ marginTop: 22, alignItems: "start" }}>
        {perfBars.length ? (
          <Card>
            <CardHead title="Interview rate by role family" action={<span className="sub" style={{ margin: 0 }}>what’s converting</span>} />
            <BarChart data={perfBars} max={100} />
          </Card>
        ) : null}

        {sourceBars.length ? (
          <Card>
            <CardHead title="Applications by source" />
            <BarChart data={sourceBars} />
          </Card>
        ) : null}

        <Card>
          <CardHead title="Match-score distribution" action={<span className="sub" style={{ margin: 0 }}>{scores.length} scored roles</span>} />
          <BarChart data={scoreBars} />
        </Card>

        {familyBars.length ? (
          <Card>
            <CardHead title="Role-family mix" />
            <BarChart data={familyBars} />
          </Card>
        ) : null}

        {companyBars.length ? (
          <Card>
            <CardHead title="Top companies hiring" />
            <BarChart data={companyBars} size="sm" />
          </Card>
        ) : null}

        <Card>
          <CardHead title="Remote vs on-site" />
          <BarChart data={remoteBars} />
        </Card>
      </div>

      {/* Salary insight */}
      {salaried.length ? (
        <>
          <h2 className="section">Salary insight<span className="sub">from {salaried.length} roles with a published range (LPA)</span></h2>
          <div className="grid cols-3">
            <Card><Stat label="Lowest" value={`${salLow.toFixed(1)}`} foot="LPA" /></Card>
            <Card accent><Stat label="Median" value={`${salMed.toFixed(1)}`} foot="LPA" /></Card>
            <Card><Stat label="Highest" value={`${salHigh.toFixed(1)}`} foot="LPA" /></Card>
          </div>
        </>
      ) : null}

      <p className="note center" style={{ marginTop: 24 }}>
        All figures are computed live from the agent’s mirror — no placeholder data.
      </p>
    </>
  );
}
