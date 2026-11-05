"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { createClient } from "@/utils/supabase/client";

// Shown only after sign-in.
const APP_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/jobs", label: "Jobs" },
  { href: "/applications", label: "Applications" },
  { href: "/get-started", label: "Job hunt" },
];

export default function Nav() {
  const path = usePathname();
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? null));
    const { data: sub } = supabase.auth.onAuthStateChange((_e, session) =>
      setEmail(session?.user?.email ?? null),
    );
    return () => sub.subscription.unsubscribe();
  }, []);

  async function signOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    setEmail(null);
    router.push("/");
    router.refresh();
  }

  return (
    <header className="top">
      <Link href="/" style={{ textDecoration: "none" }}>
        <h1 title="Error Makes Clever">EMC <span style={{ color: "var(--muted)", fontWeight: 500 }}>· Error Makes Clever</span></h1>
      </Link>
      {email ? (
        <nav>
          {APP_LINKS.map((l) => (
            <Link key={l.href} href={l.href} className={path === l.href ? "on" : ""}>
              {l.label}
            </Link>
          ))}
        </nav>
      ) : null}
      <span className="badge">
        {email ? (
          <>
            {email} ·{" "}
            <a href="#" onClick={(e) => { e.preventDefault(); signOut(); }}>Sign out</a>
          </>
        ) : (
          <Link href="/login">Sign in</Link>
        )}
      </span>
    </header>
  );
}
