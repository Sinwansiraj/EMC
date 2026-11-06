"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { createClient } from "@/utils/supabase/client";
import { Card } from "@/components/ui";

const FRUSTRATIONS = [
  {
    icon: "🪫",
    title: "Emotional exhaustion",
    body: "Applying with little response leaves you drained and unmotivated — repeated rejections feed self-doubt and frustration.",
  },
  {
    icon: "🎯",
    title: "Lack of motivation",
    body: "Finding the energy to keep applying to new openings, day after day, gets harder the longer the search drags on.",
  },
  {
    icon: "😰",
    title: "Anxiety & stress",
    body: "Worrying about finances, the future, and how employers perceive you adds a real emotional toll to the search.",
  },
];

const STEPS = [
  { icon: "📄", title: "A resume per role", body: "Add every role you target and attach a tailored resume for each. The agent maps the right one to every job." },
  { icon: "🔎", title: "Scored & shortlisted", body: "It scores and shortlists roles that actually fit, so you stop applying into the void." },
  { icon: "✅", title: "Prepared for approval", body: "Each application is prepared for your review — nothing is ever sent without you." },
  { icon: "📊", title: "Tracked end to end", body: "Every application and outcome is tracked, so the search stays calm and in your control." },
];

export default function Landing() {
  const [signedIn, setSignedIn] = useState<boolean | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setSignedIn(!!data.user));
  }, []);

  return (
    <div className="landing">
      <section className="hero">
        <span className="kicker">◆ EMC · Error Makes Clever</span>
        <h1>
          A job hunter that keeps going <span className="grad">when the search wears you down.</span>
        </h1>
        <p className="lede">
          EMC is an AI-assisted career platform. It finds roles that fit you, tailors a resume and
          cover letter for each, and prepares applications for your review — so the repetitive,
          draining part of the search is handled, and you stay in control of every decision.
        </p>
        <div className="cta">
          {signedIn ? (
            <Link className="btn lg" href="/dashboard">Go to your dashboard →</Link>
          ) : (
            <>
              <Link className="btn lg" href="/login?mode=signup">Create your account</Link>
              <Link className="btn lg ghost" href="/login">Sign in</Link>
            </>
          )}
        </div>
        <p className="note">Create an account, confirm your email, and start your hunt — free.</p>
      </section>

      <section>
        <h2 className="section">Manual job searching can wear you out<span className="sub">the frustration usually comes from three places</span></h2>
        <div className="grid cols-3">
          {FRUSTRATIONS.map((f) => (
            <Card className="feature" key={f.title} hover>
              <div className="ic" aria-hidden>{f.icon}</div>
              <h3>{f.title}</h3>
              <p className="muted mb-0">{f.body}</p>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <h2 className="section">How EMC helps<span className="sub">protect your energy; let the agent carry the grind</span></h2>
        <div className="grid cols-2">
          {STEPS.map((s, i) => (
            <Card className="feature" key={s.title} hover>
              <div className="cluster" style={{ justifyContent: "space-between" }}>
                <div className="ic" aria-hidden>{s.icon}</div>
                <span className="chip outline">Step {i + 1}</span>
              </div>
              <h3>{s.title}</h3>
              <p className="muted mb-0">{s.body}</p>
            </Card>
          ))}
        </div>

        <Card accent style={{ marginTop: 18 }}>
          <div className="cluster" style={{ justifyContent: "space-between", gap: 18 }}>
            <div>
              <h3 style={{ color: "var(--ink)", fontSize: 16, textTransform: "none", letterSpacing: "-0.01em", margin: "0 0 4px" }}>
                Human approval stays central
              </h3>
              <p className="muted mb-0" style={{ maxWidth: "52ch" }}>
                Prioritise self-care and a positive mindset — EMC handles discovery, scoring and
                preparation, and every application waits for your approval before it goes anywhere.
              </p>
            </div>
            {signedIn ? (
              <Link className="btn" href="/get-started">Continue your job hunt →</Link>
            ) : (
              <Link className="btn" href="/login?mode=signup">Get started free</Link>
            )}
          </div>
        </Card>
      </section>
    </div>
  );
}
