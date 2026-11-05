"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { createClient } from "@/utils/supabase/client";

function LoginForm() {
  const params = useSearchParams();
  const [mode, setMode] = useState<"signin" | "signup">(
    params.get("mode") === "signup" ? "signup" : "signin",
  );
  const [step, setStep] = useState<"form" | "code">("form");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  function switchMode(m: "signin" | "signup") {
    setMode(m);
    setStep("form");
    setError(null);
    setMsg(null);
  }

  async function submitForm(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMsg(null);
    if (!email.trim()) return setError("Enter your email.");
    if (password.length < 6) return setError("Password must be at least 6 characters.");
    const supabase = createClient();

    if (mode === "signin") {
      setBusy(true);
      const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
      if (!error) { window.location.assign("/get-started"); return; }
      // Account exists but email isn't verified yet → send a code and verify.
      if (/confirm/i.test(error.message)) {
        await supabase.auth.resend({ type: "signup", email: email.trim() });
        setBusy(false);
        setStep("code");
        setMsg("Verify your email to finish signing in — we emailed you a code.");
        return;
      }
      setBusy(false);
      return setError(error.message);
    }

    // signup
    if (!fullName.trim()) return setError("Enter your name.");
    if (!phone.trim()) return setError("Enter your phone number.");
    setBusy(true);
    const { data, error } = await supabase.auth.signUp({
      email: email.trim(),
      password,
      options: { data: { full_name: fullName.trim(), phone: phone.trim() } },
    });
    setBusy(false);
    if (error) return setError(error.message);
    if (data.session) { window.location.assign("/get-started"); return; } // confirmation disabled
    setStep("code");
    setMsg(`We emailed a verification code to ${email.trim()}.`);
  }

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (code.trim().length < 6) return setError("Enter the code from your email.");
    setBusy(true);
    const supabase = createClient();
    let res = await supabase.auth.verifyOtp({ email: email.trim(), token: code.trim(), type: "signup" });
    if (res.error) {
      res = await supabase.auth.verifyOtp({ email: email.trim(), token: code.trim(), type: "email" });
    }
    setBusy(false);
    if (res.error) return setError(res.error.message);
    window.location.assign("/get-started");
  }

  const title = step === "code" ? "Verify your email" : mode === "signin" ? "Sign in" : "Create your account";

  return (
    <div style={{ maxWidth: 440, margin: "40px auto" }}>
      <h2 className="section" style={{ marginTop: 0 }}>
        {title}
        <span className="sub">
          {step === "code" ? "enter the code we emailed you" : mode === "signin" ? "with your email and password" : "we'll verify your email with a code"}
        </span>
      </h2>

      {step === "form" ? (
        <form className="card" onSubmit={submitForm}>
          <div style={{ display: "grid", gap: 14 }}>
            {mode === "signup" ? (
              <>
                <div>
                  <label className="field">Full name</label>
                  <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Your name" autoFocus required />
                </div>
                <div>
                  <label className="field">Phone number</label>
                  <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91 98765 43210" required />
                </div>
              </>
            ) : null}
            <div>
              <label className="field">Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com" autoFocus={mode === "signin"} required />
            </div>
            <div>
              <label className="field">Password</label>
              <input type="password" value={password} minLength={6} onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === "signup" ? "Create a password (min 6 chars)" : "Your password"} required />
            </div>
            {error ? <div className="error">{error}</div> : null}
            <button className="btn" type="submit" disabled={busy}>
              {busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
            </button>
          </div>
        </form>
      ) : (
        <form className="card" onSubmit={verify}>
          <div style={{ display: "grid", gap: 14 }}>
            {msg ? <div className="note" style={{ color: "var(--good)" }}>{msg}</div> : null}
            <div>
              <label className="field">Verification code</label>
              <input inputMode="numeric" pattern="[0-9]*" maxLength={10} value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                placeholder="Enter the code from your email" autoFocus required
                style={{ letterSpacing: "0.3em", fontSize: 18, textAlign: "center" }} />
            </div>
            {error ? <div className="error">{error}</div> : null}
            <button className="btn" type="submit" disabled={busy}>{busy ? "Verifying…" : "Verify & continue"}</button>
          </div>
        </form>
      )}

      {step === "form" ? (
        <p className="note" style={{ textAlign: "center", marginTop: 14 }}>
          {mode === "signin" ? (
            <>New to EMC? <a href="#" onClick={(e) => { e.preventDefault(); switchMode("signup"); }}>Create an account</a></>
          ) : (
            <>Already have an account? <a href="#" onClick={(e) => { e.preventDefault(); switchMode("signin"); }}>Sign in</a></>
          )}
        </p>
      ) : null}
    </div>
  );
}

export default function Login() {
  return (
    <Suspense fallback={<div className="empty">Loading…</div>}>
      <LoginForm />
    </Suspense>
  );
}
