/** Maps agent status strings to a semantic tone + human label.
 *  Single source of truth so every status badge across the app agrees.
 *  Statuses come from the Python agent read-model (jobs.status, applications.status). */

export type Tone = "good" | "warn" | "bad" | "info" | "neutral";

const TONES: Record<string, Tone> = {
  // positive / progressing
  offer: "good",
  interview: "good",
  approved: "good",
  submitted: "good",
  applied: "good",
  done: "good",
  // needs a human / in-flight review
  prepared: "warn",
  awaiting_approval: "warn",
  needs_human: "warn",
  submitted_unverified: "warn",
  queued: "warn",
  searching: "info",
  scored: "info",
  new: "info",
  // negative
  rejected: "bad",
  withdrawn: "bad",
  failed: "bad",
  no_response: "neutral",
  filtered: "neutral",
};

/** Statuses that mean "an application actually went out". Mirrors the agent's
 *  job_agent/tracker.py SUBMITTED_LIKE (the source of truth) so dashboard,
 *  intelligence and the agent funnel all count submissions the same way —
 *  including the terminal `rejected` / `no_response` outcomes. ("applied" is an
 *  accepted legacy alias for "submitted".) */
export const SUBMITTED_LIKE = [
  "submitted",
  "submitted_unverified",
  "applied",
  "interview",
  "offer",
  "rejected",
  "no_response",
] as const;

/** Positive outcomes used as the numerator of conversion rates. */
export const POSITIVE = ["interview", "offer"] as const;

export function toneFor(status?: string | null): Tone {
  if (!status) return "neutral";
  return TONES[status] ?? "neutral";
}

export function labelFor(status?: string | null): string {
  if (!status) return "—";
  return status.replace(/_/g, " ");
}
