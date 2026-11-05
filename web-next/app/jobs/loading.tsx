import { PageHead, TableSkeleton } from "@/components/ui";

export default function Loading() {
  return (
    <>
      <PageHead title="Job Discovery" subtitle="Loading discovered & scored roles…" />
      <TableSkeleton rows={8} cols={5} />
    </>
  );
}
