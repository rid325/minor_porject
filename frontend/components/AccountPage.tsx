"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AccountProfile, AuthUser, changePassword, getAccountProfile, getAuthStatus, logOut } from "@/lib/auth";
import { clearLocalProfileData, mergeProfile } from "@/lib/profile";
import { Profile } from "@/lib/types";

export default function AccountPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    getAuthStatus().then(async (auth) => {
      if (!active) return;
      if (!auth.authenticated || !auth.user) { router.replace("/login"); return; }
      setUser(auth.user);
      try {
        const saved: AccountProfile = await getAccountProfile();
        if (active) setProfile(saved.profile ? mergeProfile(saved.profile) : null);
      } catch { if (active) setError("We could not load your saved information. Please try again."); }
    }).catch(() => { if (active) router.replace("/login"); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [router]);

  async function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setMessage("");
    if (newPassword !== confirmPassword) { setError("The new passwords do not match."); return; }
    if (newPassword.length < 8) { setError("Use at least 8 characters for your new password."); return; }
    setSaving(true);
    try {
      await changePassword(currentPassword, newPassword);
      setMessage("Your password has been changed.");
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "We could not change your password."); }
    finally { setSaving(false); }
  }

  async function signOut() {
    try { await logOut(); } finally { clearLocalProfileData(); window.location.assign("/"); }
  }

  if (loading || !user) return <main className="page-wrap"><div className="loading" style={{ minHeight: 450 }}>Loading your account…</div></main>;
  const answers = profile ? [profile.location.state, profile.location.district, profile.personal.date_of_birth, profile.personal.gender, profile.household.family_income, profile.household.bpl_status, profile.education.student_status, profile.employment.employment_status, profile.agriculture.farmer_status, profile.social.social_category, profile.social.has_savings_bank_account].filter(Boolean).length : 0;
  const schemeAnswerCount = profile ? Object.values(profile.scheme_answers || {}).reduce((sum, fields) => sum + Object.keys(fields).length, 0) : 0;

  return <main className="page-wrap account-page"><div className="page-intro"><span className="eyebrow">Your account</span><h1>Your information,<br /><span style={{ color: "var(--brand)" }}>all in one place.</span></h1><p>Manage your sign-in details and the answers used to personalise scheme matches.</p></div>
    <div className="account-grid"><section className="account-panel"><div className="account-heading"><span className="account-avatar" aria-hidden="true">{user.email.slice(0, 1).toUpperCase()}</span><div><span className="eyebrow">Email account</span><h2>{user.email}</h2></div></div><h3 className="account-subheading">Your saved information</h3><div className="account-details"><AccountDetail label="Account created" value={new Date(user.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}/><AccountDetail label="State / UT" value={profile?.location.state}/><AccountDetail label="District" value={profile?.location.district}/><AccountDetail label="Date of birth" value={profile?.personal.date_of_birth}/><AccountDetail label="Gender" value={pretty(profile?.personal.gender)}/><AccountDetail label="Applicant + spouse annual income" value={profile?.household.family_income ? `INR ${Number(profile.household.family_income).toLocaleString("en-IN")}` : ""}/><AccountDetail label="BPL status" value={pretty(profile?.household.bpl_status)}/><AccountDetail label="Currently studying" value={pretty(profile?.education.student_status)}/><AccountDetail label="Work situation" value={pretty(profile?.employment.employment_status)}/><AccountDetail label="Farmer" value={pretty(profile?.agriculture.farmer_status)}/><AccountDetail label="Social category" value={pretty(profile?.social.social_category)}/><AccountDetail label="Savings bank / post-office account" value={pretty(profile?.social.has_savings_bank_account)}/><AccountDetail label="Saved answers" value={`${answers} common · ${schemeAnswerCount} scheme-specific`}/></div>{schemeAnswerCount > 0 && <div className="account-scheme-answers"><h3>Extra details saved for schemes</h3>{Object.entries(profile?.scheme_answers || {}).map(([schemeId, fields]) => <div className="account-scheme-answer" key={schemeId}><strong>{schemeId.replaceAll("_", " ")}</strong><ul>{Object.entries(fields).map(([field, answer]) => <li key={field}>{field.replaceAll("_", " ").replaceAll(".", " · ")}: {prettyAnswer(answer)}</li>)}</ul></div>)}</div>}<div className="account-actions"><Link className="btn btn-primary" href="/profile">Edit my information <span aria-hidden="true">→</span></Link><Link className="btn btn-secondary" href="/results">View personalised schemes <span aria-hidden="true">→</span></Link></div><p className="account-note">Your common answers and any extra details you add for individual schemes are saved to your account.</p></section>
      <section className="account-panel password-panel"><span className="eyebrow">Security</span><h2>Change password</h2><p>Enter your current password, then choose a new one with at least 8 characters.</p>{error && <div className="error-banner" role="alert">{error}</div>}{message && <div className="success-banner" role="status">{message}</div>}<form className="auth-form" onSubmit={submitPassword}><div className="form-field"><label htmlFor="current-password">Current password</label><input className="field" id="current-password" type="password" autoComplete="current-password" minLength={8} maxLength={128} value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required /></div><div className="form-field"><label htmlFor="new-password">New password</label><input className="field" id="new-password" type="password" autoComplete="new-password" minLength={8} maxLength={128} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required /></div><div className="form-field"><label htmlFor="confirm-password">Confirm new password</label><input className="field" id="confirm-password" type="password" autoComplete="new-password" minLength={8} maxLength={128} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required /></div><button className="btn btn-primary" type="submit" disabled={saving}>{saving ? "Updating…" : "Update password"}</button></form></section></div>
    <div className="account-logout"><span>Finished for now?</span><button className="btn btn-ghost" type="button" onClick={signOut}>Sign out</button></div>
  </main>;
}

function AccountDetail({ label, value }: { label: string; value?: string | number }) {
  return <div><span>{label}</span><strong>{value || "Not provided"}</strong></div>;
}

function pretty(value?: string) {
  if (!value) return "";
  const labels: Record<string, string> = { yes: "Yes", no: "No", unknown: "I don’t know", woman: "Woman", man: "Man", non_binary: "Non-binary", prefer_not_to_say: "Prefer not to say", sc: "SC", st: "ST", obc: "OBC", general: "General", self_employed: "Self-employed", unemployed: "Not working", student: "Student", retired: "Retired" };
  return labels[value] || value;
}

function prettyAnswer(value: string) {
  if (value === "yes") return "Yes";
  if (value === "no") return "No";
  if (value === "unknown") return "I don’t know";
  return value;
}
