"use client";

import { useEffect, useId, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { checkEligibility } from "@/lib/api";
import { clearLocalProfileData, emptyProfile, mergeProfile, PROFILE_OWNER_KEY, PROFILE_STORAGE_KEY, RESULTS_STORAGE_KEY, profileAnswerCount } from "@/lib/profile";
import { getAccountProfile, getAuthStatus, saveAccountProfile } from "@/lib/auth";
import { Profile } from "@/lib/types";

type SectionKey = Exclude<keyof Profile, "scheme_answers" | "review">;
type FormStep = SectionKey | "review";
const sections: { key: FormStep; label: string; description: string }[] = [
  { key: "location", label: "Location", description: "Where do you live right now?" },
  { key: "personal", label: "About you", description: "A few details used by many eligibility rules." },
  { key: "household", label: "Household & income", description: "Basic household information that commonly affects support." },
  { key: "education", label: "Study", description: "Study status, used for student support schemes." },
  { key: "employment", label: "Work", description: "Your current work situation." },
  { key: "agriculture", label: "Farming", description: "Farmer status, used for agriculture schemes." },
  { key: "social", label: "Social category & banking", description: "Only a couple of common eligibility details." },
  { key: "review", label: "Review", description: "Check your answers before running a match." },
];

export default function ProfileForm() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [step, setStep] = useState(0);
  const [loadFailed, setLoadFailed] = useState(false);
  const [ready, setReady] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [accountEmail, setAccountEmail] = useState("");
  const [syncStatus, setSyncStatus] = useState("Loading your saved information…");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function loadProfile() {
      let initial = emptyProfile();
      try {
        const stored = window.localStorage.getItem(PROFILE_STORAGE_KEY);
        if (stored) initial = mergeProfile(JSON.parse(stored));
      } catch { /* A private browser mode may block local storage. */ }
      const auth = await getAuthStatus().catch(() => null);
      if (!active) return;
      const signedIn = Boolean(auth?.authenticated);
      setAuthenticated(signedIn);
      if (auth?.user?.email) setAccountEmail(auth.user.email);
      const localOwner = window.localStorage.getItem(PROFILE_OWNER_KEY);
      if (!auth && localOwner) { setLoadFailed(true); return; }
      if (localOwner && localOwner !== auth?.user?.email) {
        clearLocalProfileData();
        initial = emptyProfile();
      }
      if (signedIn) {
        try {
          const saved = await getAccountProfile();
          if (saved.profile) initial = mergeProfile(saved.profile);
          setSyncStatus(saved.updated_at ? `Saved to your account · Updated ${new Date(saved.updated_at).toLocaleDateString("en-IN")}` : "Your account profile is ready to save.");
        } catch {
          setSyncStatus("Account sync is unavailable. Your answers remain saved in this browser.");
        }
      } else {
        setSyncStatus("Sign in to keep your answers saved to your account.");
      }
      const requestedSection = new URLSearchParams(window.location.search).get("section");
      const requestedStep = sections.findIndex((item) => item.key === requestedSection);
      if (requestedStep >= 0) setStep(requestedStep);
      if (!active) return;
      if (auth?.user?.email) window.localStorage.setItem(PROFILE_OWNER_KEY, auth.user.email);
      if (new URLSearchParams(window.location.search).has("fromChat")) {
        try {
          const facts = JSON.parse(sessionStorage.getItem("yojana-confirmed-intake") || "{}");
          sessionStorage.removeItem("yojana-confirmed-intake");
          if (Object.keys(facts).length) setDirty(true);
          if (/^\d{4}-\d{2}-\d{2}$/.test(facts["personal.date_of_birth"] || "")) initial.personal.date_of_birth = facts["personal.date_of_birth"];
          if (/^\d{1,12}$/.test(facts["household.family_income"] || "")) initial.household.family_income = facts["household.family_income"];
          if (["single", "married", "widowed", "divorced"].includes(facts["personal.marital_status"])) initial.personal.marital_status = facts["personal.marital_status"];
          if (["Punjab", "Haryana", "Chandigarh", "Himachal Pradesh"].includes(facts["location.state"])) initial.location.state = facts["location.state"];
          if (["yes","no"].includes(facts["education.student_status"])) initial.education.student_status = facts["education.student_status"];
          if (["yes","no"].includes(facts["agriculture.farmer_status"])) initial.agriculture.farmer_status = facts["agriculture.farmer_status"];
        } catch { /* Profile form remains available without intake. */ }
      }
      setProfile(initial);
      setReady(true);
    }
    loadProfile();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!ready) return;
    try { window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile)); } catch { /* The account copy is still available when signed in. */ }
    if (!authenticated || !dirty) return;
    setSyncStatus("Saving your answers to your account…");
    const timer = window.setTimeout(() => {
      saveAccountProfile(profile)
        .then((saved) => { if (accountEmail) window.localStorage.setItem(PROFILE_OWNER_KEY, accountEmail); setSyncStatus(saved.updated_at ? `Saved to your account · Updated ${new Date(saved.updated_at).toLocaleDateString("en-IN")}` : "Saved to your account."); })
        .catch(() => setSyncStatus("Could not sync just now. Your answers remain saved in this browser."));
    }, 600);
    return () => window.clearTimeout(timer);
  }, [profile, ready, authenticated, accountEmail, dirty]);

  const update = (section: SectionKey, field: string, value: string) => {
    setDirty(true);
    setProfile((current) => ({ ...current, [section]: { ...(current[section] as Record<string, string>), [field]: value } } as Profile));
    setError("");
  };
  const current = sections[step];
  const answers = useMemo(() => profileAnswerCount(profile), [profile]);
  const next = () => setStep((value) => Math.min(value + 1, sections.length - 1));
  const previous = () => setStep((value) => Math.max(value - 1, 0));
  const reset = () => {
    if (!window.confirm("Clear your saved profile answers from this browser and your account?")) return;
    setDirty(true); setProfile(emptyProfile()); setStep(0); setError("");
    try { window.localStorage.removeItem(PROFILE_STORAGE_KEY); window.localStorage.removeItem(RESULTS_STORAGE_KEY); } catch { /* ignore */ }
  };
  const runMatch = async () => {
    setRunning(true); setError("");
    try {
      if (authenticated) await saveAccountProfile(profile);
      const result = await checkEligibility(profile);
      window.localStorage.setItem(RESULTS_STORAGE_KEY, JSON.stringify(result));
      router.push("/results");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We could not run the check yet. Please try again.");
    } finally { setRunning(false); }
  };

  if (loadFailed) return <main className="page-wrap page-intro"><h1>Account temporarily unavailable</h1><p>Your saved answers are still in this browser.</p><button className="btn btn-primary" onClick={() => window.location.reload()}>Retry</button></main>;
  if (!ready) return <main className="page-wrap"><div className="loading" style={{ minHeight: 440 }}>Loading your saved answers…</div></main>;

  return (
    <main className="form-page">
      <div className="page-wrap page-intro"><span className="eyebrow">Your private profile</span><h1>Edit your information<br /><span style={{ color: "var(--brand)" }}>whenever you need.</span></h1><p>Your answers are saved to your account when you are signed in. Revisit this page any time to update them before checking your scheme matches.</p><div className="account-actions"><Link className="btn btn-primary" href="/chat">Go to chatbot</Link><Link className="btn btn-secondary" href="/document-checker">Open document mismatch checker</Link></div></div>
      <div className="page-wrap form-shell">
        <aside className="form-nav" aria-label="Profile sections"><div className="form-nav-title">Your progress</div>{sections.map((item, index) => <button className={`form-step ${index === step ? "active" : ""}`} key={item.key} onClick={() => setStep(index)}><span className="step-number">{index + 1}</span><span>{item.label}</span></button>)}</aside>
        <div className="form-content">
          <div className="save-banner"><div><strong>{ready ? syncStatus : "Loading your saved information…"}</strong><br /><span>{authenticated ? "Only your account can access these saved answers." : "Sign in to sync answers across devices; no identity or document numbers are requested."}</span></div><button className="btn btn-danger btn-small" onClick={reset}>Reset</button></div>
          {error && <div className="error-banner" role="alert" style={{ marginBottom: 15 }}>{error}</div>}
          <section className="form-card" aria-labelledby="profile-step-title">
            <div className="progress-row" aria-label={`Step ${step + 1} of ${sections.length}`}>{sections.map((item, index) => <span className={`progress-segment ${index <= step ? "done" : ""}`} key={item.key} />)}</div>
            {step < sections.length - 1 ? <><h2 id="profile-step-title">{current.description}</h2><p>These fields help us compare your situation with scheme rules. You can change anything later.</p><StepFields section={current.key as SectionKey} profile={profile} update={update} /></> : <Review profile={profile} answers={answers} />}
            <div className="form-actions"><button className="btn btn-ghost" onClick={previous} disabled={step === 0}>← Back</button><div className="action-right">{step < sections.length - 1 ? <button className="btn btn-primary" onClick={next}>Continue <span aria-hidden="true">→</span></button> : <button className="btn btn-primary" onClick={runMatch} disabled={running}>{running ? "Checking…" : "See my matches ↗"}</button>}</div></div>
          </section>
        </div>
      </div>
    </main>
  );
}

function StepFields({ section, profile, update }: { section: SectionKey; profile: Profile; update: (section: SectionKey, field: string, value: string) => void }) {
  const values = profile[section] as Record<string, string>;
  const field = (name: string) => values[name] || "";
  if (section === "location") return <div className="form-grid"><TextField label="State or Union Territory" value={field("state")} onChange={(value) => update(section, "state", value)} placeholder="e.g. Punjab" help="Used to find state-specific routes." /><TextField label="District" value={field("district")} onChange={(value) => update(section, "district", value)} placeholder="e.g. Ludhiana" /><TextField label="Postal PIN (optional)" value={field("pin")} onChange={(value) => update(section, "pin", value)} help="Used for document comparison." /><ChoiceField label="Where do you live?" value={field("residence_type")} onChange={(value) => update(section, "residence_type", value)} options={[["rural", "Rural"], ["urban", "Urban"], ["unknown", "I don’t know"]]} /><ChoiceField label="Are you domiciled in this state?" value={field("domicile")} onChange={(value) => update(section, "domicile", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"]]} /> </div>;
  if (section === "personal") return <div className="form-grid"><TextField label="Name as shown on your documents (optional)" value={field("name")} onChange={(value) => update(section, "name", value)} help="Used for document comparison." /><TextField label="Date of birth" type="date" value={field("date_of_birth")} onChange={(value) => update(section, "date_of_birth", value)} help="Used to calculate age for age-based schemes." /><ChoiceField label="Marital status" value={field("marital_status")} onChange={value => update(section, "marital_status", value)} options={[["single","Single"],["married","Married"],["widowed","Widowed"],["divorced","Divorced"]]} /><ChoiceField label="Gender" value={field("gender")} onChange={(value) => update(section, "gender", value)} options={[["woman", "Woman"], ["man", "Man"], ["non_binary", "Non-binary"], ["prefer_not_to_say", "Prefer not to say"]]} /></div>;
  if (section === "household") return <div className="form-grid"><TextField label="Total annual household income (INR)" type="number" value={field("family_income")} onChange={(value) => update(section, "family_income", value)} placeholder="Optional" help="Leave blank if you do not know." /><ChoiceField label="Does your household have BPL status?" value={field("bpl_status")} onChange={(value) => update(section, "bpl_status", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"]]} /></div>;
  if (section === "education") return <div className="form-grid"><ChoiceField label="Are you currently studying?" value={field("student_status")} onChange={(value) => update(section, "student_status", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"]]} /></div>;
  if (section === "employment") return <div className="form-grid"><ChoiceField label="Current work situation" value={field("employment_status")} onChange={(value) => update(section, "employment_status", value)} options={[["employed", "Employed"], ["self_employed", "Self-employed"], ["unemployed", "Not working"], ["student", "Student"], ["retired", "Retired"], ["unknown", "I don’t know"]]} /></div>;
  if (section === "agriculture") return <div className="form-grid"><ChoiceField label="Are you a farmer?" value={field("farmer_status")} onChange={(value) => update(section, "farmer_status", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"]]} /></div>;
  return <div className="form-grid"><ChoiceField label="Social category (optional; only relevant to some schemes)" value={field("social_category")} onChange={(value) => update(section, "social_category", value)} options={[["general", "General"], ["sc", "SC"], ["st", "ST"], ["obc", "OBC"], ["other", "Other"], ["prefer_not_to_say", "Prefer not to say"]]} /><ChoiceField label="Do you have a savings bank or post-office account?" value={field("has_savings_bank_account")} onChange={(value) => update(section, "has_savings_bank_account", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"]]} /></div>;
}

function TextField({ label, value, onChange, placeholder, help, type = "text" }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string; help?: string; type?: string }) { const id = useId(); return <div className="form-field"><label htmlFor={id}>{label}</label><input id={id} className="field" type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />{help && <span className="form-help">{help}</span>}</div>; }
function ChoiceField({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[][] }) { const name = label.toLowerCase().replace(/[^a-z0-9]+/g, "-"); return <div className="form-field full"><span style={{ fontSize: 12, fontWeight: 700 }}>{label}</span><div className="radio-grid">{options.map(([option, text]) => <div className="choice" key={option}><input id={`${name}-${option}`} type="radio" name={name} checked={value === option} onChange={() => onChange(option)} /><label htmlFor={`${name}-${option}`}>{text}</label></div>)}</div></div>; }

function Review({ profile, answers }: { profile: Profile; answers: number }) {
  const value = (section: keyof Profile, key: string) => String((profile[section] as Record<string, string>)[key] || "Not answered");
  return <><h2 id="profile-step-title">A quick review</h2><p>You have answered {answers} questions. Blank and “I don’t know” answers will show up as follow-ups rather than exclusions.</p><div className="review-box"><div className="review-line"><span>Location</span><strong>{value("location", "state")}{profile.location.district ? ` · ${profile.location.district}` : ""}</strong></div><div className="review-line"><span>Household income</span><strong>{profile.household.family_income ? `INR ${Number(profile.household.family_income).toLocaleString("en-IN")}` : "Not answered"}</strong></div><div className="review-line"><span>Work situation</span><strong>{value("employment", "employment_status")}</strong></div><div className="review-line"><span>Farmer status</span><strong>{value("agriculture", "farmer_status")}</strong></div><div className="review-line"><span>Social category</span><strong>{value("social", "social_category")}</strong></div></div><p style={{ marginTop: 18, marginBottom: 0, fontSize: 12 }}>Your answers are saved to your account when you are signed in. Open your profile icon to return here and edit them.</p></>;
}


