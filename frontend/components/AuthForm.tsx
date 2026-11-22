"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { logIn, signUp } from "@/lib/auth";

type Props = { mode: "login" | "signup" };

export default function AuthForm({ mode }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const isSignup = mode === "signup";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (isSignup) await signUp(email.trim(), password);
      else await logIn(email.trim(), password);
      window.location.assign(isSignup ? "/schemes" : "/");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We could not sign you in. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page page-wrap">
      <section className="auth-layout" aria-labelledby="auth-title">
        <div className="auth-story"><span className="auth-mark" aria-hidden="true">Y</span><span className="eyebrow">Yojna Connect</span><h1>Public support,<br /><em>made easier to find.</em></h1><p>Explore government schemes, understand the requirements and see which reviewed conditions match your situation.</p><div className="auth-points"><span><b>01</b> Browse schemes by state and sector</span><span><b>02</b> See matched conditions clearly</span><span><b>03</b> Check official sources before applying</span></div><small>Your profile answers stay in this browser.</small></div>
        <div className="auth-card"><div className="auth-card-heading"><span className="eyebrow">{isSignup ? "Get started" : "Your account"}</span><h2 id="auth-title">{isSignup ? "Create your account" : "Welcome back"}</h2><p>{isSignup ? "Sign up with just your email and a password." : "Sign in to continue to Yojna Connect."}</p></div>

        {error && <div className="error-banner auth-error" role="alert">{error}</div>}

        <form className="auth-form" onSubmit={submit}>
          <div className="form-field">
            <label htmlFor="account-email">Email address</label>
            <input
              className="field"
              id="account-email"
              name="email"
              type="email"
              autoComplete="email"
              maxLength={254}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>
          <div className="form-field">
            <label htmlFor="account-password">Password</label>
            <input
              className="field"
              id="account-password"
              name="password"
              type="password"
              autoComplete={isSignup ? "new-password" : "current-password"}
              minLength={8}
              maxLength={128}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
            {isSignup && <span className="form-help">Use at least 8 characters.</span>}
          </div>
          <button className="btn btn-primary auth-submit" type="submit" disabled={submitting}>
            {submitting ? "Please wait…" : isSignup ? "Create account" : "Sign in"}
          </button>
        </form>

        <p className="auth-switch">
          {isSignup ? "Already have an account?" : "New to Yojna Connect?"}{" "}
          <Link href={isSignup ? "/login" : "/signup"}>{isSignup ? "Sign in" : "Create an account"}</Link>
        </p>
        <p className="auth-private">We only ask for an email and password to create your account. No phone number or personal details are required.</p></div>
      </section>
    </main>
  );
}
