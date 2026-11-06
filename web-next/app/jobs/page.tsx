import Link from "next/link";
import { db } from "@/lib/supabase";
import type { Job } from "@/lib/types";
import { PageHead, ErrorState, EmptyState } from "@/components/ui";
import JobsExplorer from "./JobsExplorer";

export const revalidate = 60;

export default async function JobsPage() {
  const supabase = await db();
  const { data: jobs, error } = await supabase
    .from("jobs")
    .select("*")
    .order("score", { ascending: false });

  if (error) {
    return (
      <>
        <PageHead title="Job Discovery" />
        <ErrorState title="Couldn’t load jobs">{error.message}</ErrorState>
      </>
    );
  }

  if (!jobs?.length) {
    return (
      <>
        <PageHead title="Job Discovery" subtitle="Roles the agent found and scored for you." />
        <EmptyState
          icon="🔎"
          title="No jobs discovered yet"
          action={<Link className="btn" href="/get-started">Set up your job hunt →</Link>}
        >
          Run the agent and sync to Supabase to see discovered roles here.
        </EmptyState>
      </>
    );
  }

  return (
    <>
      <PageHead
        title="Job Discovery"
        subtitle={`${jobs.length} roles discovered & scored by the agent.`}
      />
      <JobsExplorer jobs={jobs as Job[]} />
    </>
  );
}
