"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthUser, getAuthStatus } from "@/lib/auth";


export default function AuthNav({ compact = false }: { compact?: boolean }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    getAuthStatus()
      .then((status) => { if (active) { setUser(status.authenticated ? status.user : null); } })
      .catch(() => { if (active) setUser(null); })
      .finally(() => { if (active) setReady(true); });
    return () => { active = false; };
  }, []);

  if (!ready) return <span className={compact ? "auth-nav auth-nav-compact" : "auth-nav"} aria-hidden="true" />;
  if (user) {
    return (
      <div className={compact ? "auth-nav auth-nav-compact" : "auth-nav"}>
        <Link className="auth-profile-button" href="/account" aria-label="Open your account" title="Your account"><svg aria-hidden="true" viewBox="0 0 24 24" width="21" height="21" fill="none"><circle cx="12" cy="8" r="3.4" stroke="currentColor" strokeWidth="1.7"/><path d="M5.2 20c.55-3.55 3.1-5.4 6.8-5.4s6.25 1.85 6.8 5.4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/></svg><span className="sr-only">Account profile</span></Link>
      </div>
    );
  }
  return (
    <div className={compact ? "auth-nav auth-nav-compact" : "auth-nav"}>
      <Link className="auth-nav-link" href="/login">Sign in</Link>
      {!compact && <Link className="auth-nav-create" href="/signup">Create account</Link>}
    </div>
  );
}
