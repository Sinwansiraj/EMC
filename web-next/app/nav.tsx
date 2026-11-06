"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { createClient } from "@/utils/supabase/client";

// Shown only after sign-in. Routes are stable; labels follow the redesign.
const APP_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/jobs", label: "Discovery" },
  { href: "/applications", label: "Applications" },
  { href: "/agent", label: "Agent" },
  { href: "/intelligence", label: "Intelligence" },
  { href: "/resume-studio", label: "Resumes" },
];

export default function Nav() {
  const path = usePathname();
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? null));
    const { data: sub } = supabase.auth.onAuthStateChange((_e, session) =>
      setEmail(session?.user?.email ?? null),
    );
    return () => sub.subscription.unsubscribe();
  }, []);

  // Restore saved theme (defaults to the premium dark theme).
  useEffect(() => {
    try {
      const saved = localStorage.getItem("emc-theme");
      if (saved === "light") {
        document.documentElement.setAttribute("data-theme", "light");
        setTheme("light");
      }
    } catch {
      /* storage may be blocked — dark default is fine */
    }
    // Reflect theme changes made elsewhere (e.g. Profile preferences) so this
    // toggle never acts on stale state.
    const onTheme = (e: Event) => {
      const t = (e as CustomEvent<"dark" | "light">).detail;
      if (t === "dark" || t === "light") setTheme(t);
    };
    window.addEventListener("emc-theme", onTheme);
    return () => window.removeEventListener("emc-theme", onTheme);
  }, []);

  // Close the mobile menu on navigation.
  useEffect(() => setOpen(false), [path]);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    if (next === "light") document.documentElement.setAttribute("data-theme", "light");
    else document.documentElement.removeAttribute("data-theme");
    try {
      localStorage.setItem("emc-theme", next);
    } catch {
      /* ignore */
    }
    // Broadcast so other views (e.g. Profile preferences) stay in sync.
    try { window.dispatchEvent(new CustomEvent("emc-theme", { detail: next })); } catch { /* ignore */ }
  }

  async function signOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    setEmail(null);
    router.push("/");
    router.refresh();
  }

  return (
    <header className="top">
      <Link href="/" style={{ textDecoration: "none", color: "inherit" }}>
        <h1 title="Error Makes Clever">
          <span className="logo-mark" aria-hidden>EMC</span>
          <span>EMC</span>
          <span className="sub" style={{ marginLeft: 0 }}>Error Makes Clever</span>
        </h1>
      </Link>

      {email ? (
        <>
          <button
            className="icon-btn nav-toggle"
            aria-label="Toggle menu"
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
          >
            ☰
          </button>
          <nav className={open ? "open" : ""}>
            {APP_LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                aria-current={path === l.href ? "page" : undefined}
                className={path === l.href ? "on" : ""}
              >
                {l.label}
              </Link>
            ))}
          </nav>
        </>
      ) : null}

      <span className="badge">
        <button
          className="icon-btn"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          title="Toggle theme"
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
        {email ? (
          <>
            <Link href="/profile" className="who" title="Profile & preferences">{email}</Link>
            <a href="#" onClick={(e) => { e.preventDefault(); signOut(); }}>Sign out</a>
          </>
        ) : (
          <Link href="/login">Sign in</Link>
        )}
      </span>
    </header>
  );
}
