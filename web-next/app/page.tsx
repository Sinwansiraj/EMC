"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { createClient } from "@/utils/supabase/client";

const FRUSTRATIONS = [
  {
    title: "Emotional exhaustion",
    body: "Applying with little response leaves you drained and unmotivated — repeated rejections feed self-doubt and frustration.",
  },
  {
    title: "Lack of motivation",
    body: "Finding the energy to keep applying to new openings, day after day, gets harder the longer the search drags on.",
  },
  {
    title: "Anxiety & stress",
    body: "Worrying about finances, the future, and how employers perceive you adds a real emotional toll to the search.",
  },
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
        <span className="kicker">EMC · Error Makes Clever</span>
        <h1>A job hunter that keeps going when the search wears you down.</h1>
        <p className="lede">
          EMC is a customised job hunter. It finds roles that fit you, tailors a resume and cover
          letter for each, and prepares applications for your review — so the repetitive, draining
          part of the search is handled for you.
        </p>
        <div className="cta">
          {signedIn ? (
            <Link className="btn" href="/get-started">Go to your job hunt →</Link>
          ) : (
            <>
              <Link className="btn" href="/login?mode=signup">Create your account</Link>
              <Link className="btn ghost" href="/login">Sign in</Link>
            </>
          )}
        </div>
        <p className="note">Create an account, confirm your email, and start your hunt.</p>
      </section>

      <section>
        <h2 className="section">Manual job searching can wear you out</h2>
        <p className="lede-sm">
          Searching and applying by hand is frustrating long before you land a job. That frustration
          usually comes from three places:
        </p>
        <div className="grid">
          {FRUSTRATIONS.map((f) => (
            <div className="card" key={f.title}>
              <h3>{f.title}</h3>
              <p className="muted" style={{ margin: 0 }}>{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="section">How EMC helps</h2>
        <div className="card">
          <p style={{ marginTop: 0 }}>
            The best way to cope is to take breaks, protect your energy, and let a customised job
            hunter carry the repetitive load. EMC does exactly that:
          </p>
          <ul className="how">
            <li>Adds a resume for each role you target and matches the right one to every job.</li>
            <li>Scores and shortlists roles that actually fit, so you stop applying into the void.</li>
            <li>Prepares each application for your approval — nothing is sent without you.</li>
            <li>Tracks every application and outcome, so the search stays calm and in control.</li>
          </ul>
          <p className="muted" style={{ marginBottom: 0 }}>
            Prioritise self-care and a positive mindset — let EMC handle the grind.
          </p>
        </div>
        <div className="cta" style={{ marginTop: 20 }}>
          {signedIn ? (
            <Link className="btn" href="/get-started">Continue your job hunt →</Link>
          ) : (
            <Link className="btn" href="/login?mode=signup">Get started free</Link>
          )}
        </div>
      </section>
    </div>
  );
}
