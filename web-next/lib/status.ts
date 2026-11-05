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
  filtered: "neutral",
};

export function toneFor(status?: string | null): Tone {
  if (!status) return "neutral";
  return TONES[status] ?? "neutral";
}

export function labelFor(status?: string | null): string {
  if (!status) return "—";
  return status.replace(/_/g, " ");
}
