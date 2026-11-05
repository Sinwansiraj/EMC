import { cookies } from "next/headers";
import { createClient } from "@/utils/supabase/server";

/** Server-side Supabase client for read-only showcase queries (anon key + RLS). */
export async function db() {
  const cookieStore = await cookies();
  return createClient(cookieStore);
}
