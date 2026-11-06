/** Agent role families (job_agent/tailor.py FAMILY_FOCUS). A resume's target_role
 *  uses these codes so it maps onto the agent's per-family master resume. */
export const ROLES: { code: string; label: string }[] = [
  { code: "data_analyst", label: "Data Analyst" },
  { code: "data_scientist", label: "Data Scientist" },
  { code: "ai_ml_engineer", label: "AI / ML Engineer" },
  { code: "ai_builder", label: "AI Builder" },
  { code: "prompt_engineer", label: "Prompt Engineer" },
  { code: "customer_support_mgmt", label: "Customer Support (Management)" },
  { code: "customer_support_engineer", label: "Customer Support Engineer" },
];

export const labelForRole = (code: string) =>
  ROLES.find((r) => r.code === code)?.label ?? code;

export const parseRoles = (csv?: string | null): string[] =>
  String(csv ?? "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
