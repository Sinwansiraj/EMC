export type Job = {
  id: number;
  score: number | null;
  role_family: string | null;
  title: string;
  company: string;
  location: string | null;
  platform: string | null;
  remote: boolean;
  filter_reason: string | null;
  deadline: string | null;
  salary_min: number | null;
  salary_max: number | null;
  url: string | null;
  status: string | null;
  missing: string[] | null;
  first_seen_at: string | null;
};

export type Application = {
  id: number;
  job_id: number | null;
  status: string | null;
  resume_version: string | null;
  selection_reason: string | null;
  approval: string | null;
  submitted_at: string | null;
  follow_up_on: string | null;
  verification: string | null;
  title: string;
  company: string;
  platform: string | null;
  score: number | null;
  url: string | null;
};

export type Count = { status: string; c: number };

export type Dashboard = {
  apps_by_status: Count[];
  jobs_by_status: Count[];
  submitted_today: number;
  performance: {
    family: string | null;
    applied: number;
    interviews: number;
    rejected: number;
    avg_score: number | null;
    interview_rate: number;
  }[];
  by_source: { source: string; applied: number; interviews: number }[];
  follow_ups: { id: number; title: string; company: string; follow_up_on: string }[];
  waiting_on_you: {
    id: number;
    title: string;
    company: string;
    status: string;
    selection_reason: string | null;
    notes: string | null;
  }[];
  unverified: number;
};
