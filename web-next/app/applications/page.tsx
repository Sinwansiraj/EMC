import Link from "next/link";
import { db } from "@/lib/supabase";
import type { Application } from "@/lib/types";
import { PageHead, ErrorState, EmptyState } from "@/components/ui";
import ApplicationsBoard from "./ApplicationsBoard";

export const revalidate = 60;

export default async function ApplicationsPage() {
  const supabase = await db();
  const { data: apps, error } = await supabase
    .from("applications")
    .select("*")
    .order("score", { ascending: false });

  if (error) {
    return (
      <>
        <PageHead title="Application Center" />
        <ErrorState title="Couldn’t load applications">{error.message}</ErrorState>
      </>
    );
  }

  if (!apps?.length) {
    return (
      <>
        <PageHead title="Application Center" subtitle="Every decision the agent made, with its reasoning." />
        <EmptyState
          icon="🗂️"
          title="No applications yet"
          action={<Link className="btn" href="/jobs">Browse discovered jobs →</Link>}
        >
          Once the agent prepares applications, they’ll appear here for your review.
        </EmptyState>
      </>
    );
  }

  return (
    <>
      <PageHead
        title="Application Center"
        subtitle={`${apps.length} applications — every decision the agent made, with its reasoning.`}
      />
      <ApplicationsBoard apps={apps as Application[]} />
    </>
  );
}
