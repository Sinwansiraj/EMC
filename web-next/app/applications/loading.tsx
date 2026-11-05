import { PageHead, TableSkeleton } from "@/components/ui";

export default function Loading() {
  return (
    <>
      <PageHead title="Application Center" subtitle="Loading every decision the agent made…" />
      <TableSkeleton rows={8} cols={5} />
    </>
  );
}
