import { Card, PageHead, Skeleton, TableSkeleton } from "@/components/ui";

export default function Loading() {
  return (
    <>
      <PageHead title="Dashboard" subtitle="Loading your job-hunt activity…" />
      <div className="grid">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <Skeleton className="sk-line w-40" />
            <Skeleton className="sk-line" style={{ height: 30, width: "55%", margin: "10px 0" }} />
            <Skeleton className="sk-line w-60" />
          </Card>
        ))}
      </div>
      <h2 className="section">Waiting on you</h2>
      <TableSkeleton rows={4} cols={2} />
    </>
  );
}
