"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { checkEligibility } from "@/lib/api";
import { emptyProfile, mergeProfile, PROFILE_STORAGE_KEY, RESULTS_STORAGE_KEY, profileAnswerCount } from "@/lib/profile";
import { Profile } from "@/lib/types";

type SectionKey = Exclude<keyof Profile, "review">;
type FormStep = SectionKey | "review";
const sections: { key: FormStep; label: string; description: string }[] = [
  { key: "location", label: "Location", description: "Where do you live right now?" },
  { key: "personal", label: "Personal details", description: "A few details that some schemes use." },
  { key: "household", label: "Household & income", description: "The financial context that can affect eligibility." },
  { key: "education", label: "Education", description: "Study status and level, when relevant." },
  { key: "employment", label: "Work & occupation", description: "Your current work situation." },
  { key: "agriculture", label: "Agriculture & assets", description: "Farmer and land information." },
  { key: "social", label: "Social conditions", description: "Category and existing registrations." },
  { key: "review", label: "Review", description: "Check your answers before running a match." },
];

export default function ProfileForm() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [step, setStep] = useState(0);
  const [saved, setSaved] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(PROFILE_STORAGE_KEY);
      if (stored) setProfile(mergeProfile(JSON.parse(stored)));
    } catch { /* A private browser mode may block local storage. */ }
  }, []);

  useEffect(() => {
    try { window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile)); setSaved(true); } catch { setSaved(false); }
  }, [profile]);

  const update = (section: SectionKey, field: string, value: string) => {
    setProfile((current) => ({ ...current, [section]: { ...(current[section] as Record<string, string>), [field]: value } } as Profile));
    setError("");
  };
  const current = sections[step];
  const answers = useMemo(() => profileAnswerCount(profile), [profile]);
  const next = () => setStep((value) => Math.min(value + 1, sections.length - 1));
  const previous = () => setStep((value) => Math.max(value - 1, 0));
  const reset = () => {
    if (!window.confirm("Clear the profile saved in this browser?")) return;
    setProfile(emptyProfile()); setStep(0); setError("");
    try { window.localStorage.removeItem(PROFILE_STORAGE_KEY); window.localStorage.removeItem(RESULTS_STORAGE_KEY); } catch { /* ignore */ }
  };
  const runMatch = async () => {
    setRunning(true); setError("");
    try {
      const result = await checkEligibility(profile);
      window.localStorage.setItem(RESULTS_STORAGE_KEY, JSON.stringify(result));
      router.push("/results");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We could not run the check yet. Please try again.");
    } finally { setRunning(false); }
  };

  return (
    <main className="form-page">
      <div className="page-wrap page-intro"><span className="eyebrow">Your private profile</span><h1>Let’s make the list<br /><span style={{ color: "var(--brand)" }}>more useful.</span></h1><p>Answer what you know. Leave the rest blank or mark “I don’t know”; unknown answers become a follow-up question, never an automatic rejection.</p></div>
      <div className="page-wrap form-shell">
        <aside className="form-nav" aria-label="Profile sections"><div className="form-nav-title">Your progress</div>{sections.map((item, index) => <button className={`form-step ${index === step ? "active" : ""}`} key={item.key} onClick={() => setStep(index)}><span className="step-number">{index + 1}</span><span>{item.label}</span></button>)}</aside>
        <div className="form-content">
          <div className="save-banner"><div><strong>{saved ? "Saved in this browser" : "Your answers are local"}</strong><br /><span>No account, Aadhaar, bank or document numbers.</span></div><button className="btn btn-danger btn-small" onClick={reset}>Reset</button></div>
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
  if (section === "location") return <div className="form-grid"><TextField label="State or Union Territory" value={field("state")} onChange={(value) => update(section, "state", value)} placeholder="e.g. Punjab" help="Used to find state-specific routes." /><TextField label="District" value={field("district")} onChange={(value) => update(section, "district", value)} placeholder="e.g. Ludhiana" /><ChoiceField label="Where do you live?" value={field("residence_type")} onChange={(value) => update(section, "residence_type", value)} options={[["rural", "Rural"], ["urban", "Urban"], ["unknown", "I don’t know"]]} /><ChoiceField label="Are you domiciled in this state?" value={field("domicile")} onChange={(value) => update(section, "domicile", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"]]} /> </div>;
  if (section === "personal") return <div className="form-grid"><TextField label="Date of birth" type="date" value={field("date_of_birth")} onChange={(value) => update(section, "date_of_birth", value)} help="Age is calculated from this date; it is not stored by the server." /><ChoiceField label="Gender (only used where relevant)" value={field("gender")} onChange={(value) => update(section, "gender", value)} options={[["woman", "Woman"], ["man", "Man"], ["non_binary", "Non-binary"], ["prefer_not_to_say", "Prefer not to say"]]} /><ChoiceField label="Marital status" value={field("marital_status")} onChange={(value) => update(section, "marital_status", value)} options={[["single", "Single"], ["married", "Married"], ["widowed", "Widowed"], ["divorced", "Divorced"], ["unknown", "I don’t know"]]} /><ChoiceField label="Do you have a disability?" value={field("disability_status")} onChange={(value) => update(section, "disability_status", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"], ["prefer_not_to_say", "Prefer not to say"]]} /><TextField label="Disability percentage (optional)" value={field("disability_percentage")} onChange={(value) => update(section, "disability_percentage", value)} placeholder="e.g. 40" /></div>;
  if (section === "household") return <div className="form-grid"><TextField label="Household size" type="number" value={field("size")} onChange={(value) => update(section, "size", value)} placeholder="e.g. 4" /><TextField label="Your annual income (INR)" type="number" value={field("applicant_income")} onChange={(value) => update(section, "applicant_income", value)} placeholder="Optional" /><TextField label="Household annual income (INR)" type="number" value={field("family_income")} onChange={(value) => update(section, "family_income", value)} placeholder="e.g. 240000" help="If you do not know, leave it blank." /><ChoiceField label="Income period" value={field("income_period")} onChange={(value) => update(section, "income_period", value)} options={[["annual", "Annual"], ["monthly", "Monthly"], ["unknown", "I don’t know"]]} /><ChoiceField label="BPL status" value={field("bpl_status")} onChange={(value) => update(section, "bpl_status", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"]]} /><ChoiceField label="Do you have a ration card?" value={field("ration_card")} onChange={(value) => update(section, "ration_card", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"]]} /><ChoiceField label="PPP / family ID available?" value={field("ppp_status")} onChange={(value) => update(section, "ppp_status", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"], ["prefer_not_to_say", "Prefer not to say"]]} /></div>;
  if (section === "education") return <div className="form-grid"><ChoiceField label="Are you currently studying?" value={field("student_status")} onChange={(value) => update(section, "student_status", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"]]} /><TextField label="Study level or course" value={field("study_level")} onChange={(value) => update(section, "study_level", value)} placeholder="e.g. Class 12, ITI, diploma" /><TextField label="Institution type" value={field("institution_type")} onChange={(value) => update(section, "institution_type", value)} placeholder="e.g. Government college" help="Optional; only relevant to some scholarships." /></div>;
  if (section === "employment") return <div className="form-grid"><ChoiceField label="Current work situation" value={field("employment_status")} onChange={(value) => update(section, "employment_status", value)} options={[["employed", "Employed"], ["self_employed", "Self-employed"], ["unemployed", "Not working"], ["student", "Student"], ["retired", "Retired"], ["unknown", "I don’t know"]]} /><TextField label="Occupation or work type" value={field("occupation")} onChange={(value) => update(section, "occupation", value)} placeholder="e.g. street vendor, tailor, driver" /><ChoiceField label="Registered as a worker?" value={field("worker_registration")} onChange={(value) => update(section, "worker_registration", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"]]} /><ChoiceField label="Starting or running an enterprise?" value={field("enterprise_status")} onChange={(value) => update(section, "enterprise_status", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"]]} /></div>;
  if (section === "agriculture") return <div className="form-grid"><ChoiceField label="Are you a farmer?" value={field("farmer_status")} onChange={(value) => update(section, "farmer_status", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"]]} /><ChoiceField label="Landholding status" value={field("landholding_status")} onChange={(value) => update(section, "landholding_status", value)} options={[["owned", "Own land"], ["leased", "Lease / tenant"], ["none", "No land"], ["unknown", "I don’t know"]]} /><ChoiceField label="Do you cultivate land?" value={field("cultivable_land")} onChange={(value) => update(section, "cultivable_land", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"]]} /></div>;
  return <div className="form-grid"><ChoiceField label="Social category (only where relevant)" value={field("social_category")} onChange={(value) => update(section, "social_category", value)} options={[["general", "General"], ["sc", "SC"], ["st", "ST"], ["obc", "OBC"], ["other", "Other"], ["prefer_not_to_say", "Prefer not to say"]]} /><ChoiceField label="Already receiving a government benefit?" value={field("existing_benefit")} onChange={(value) => update(section, "existing_benefit", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"]]} /><ChoiceField label="Have a required registration (if any)?" value={field("required_registration")} onChange={(value) => update(section, "required_registration", value)} options={[["yes", "Yes"], ["no", "No"], ["unknown", "I don’t know"], ["prefer_not_to_say", "Prefer not to say"]]} /></div>;
}

function TextField({ label, value, onChange, placeholder, help, type = "text" }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string; help?: string; type?: string }) { return <div className="form-field"><label>{label}</label><input className="field" type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />{help && <span className="form-help">{help}</span>}</div>; }
function ChoiceField({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[][] }) { const name = label.toLowerCase().replace(/[^a-z0-9]+/g, "-"); return <div className="form-field full"><span style={{ fontSize: 12, fontWeight: 700 }}>{label}</span><div className="radio-grid">{options.map(([option, text]) => <div className="choice" key={option}><input id={`${name}-${option}`} type="radio" name={name} checked={value === option} onChange={() => onChange(option)} /><label htmlFor={`${name}-${option}`}>{text}</label></div>)}</div></div>; }

function Review({ profile, answers }: { profile: Profile; answers: number }) {
  const value = (section: keyof Profile, key: string) => String((profile[section] as Record<string, string>)[key] || "Not answered");
  return <><h2 id="profile-step-title">A quick review</h2><p>You have answered {answers} questions. Blank and “I don’t know” answers will show up as follow-ups rather than exclusions.</p><div className="review-box"><div className="review-line"><span>Location</span><strong>{value("location", "state")}{profile.location.district ? ` · ${profile.location.district}` : ""}</strong></div><div className="review-line"><span>Household income</span><strong>{profile.household.family_income ? `INR ${Number(profile.household.family_income).toLocaleString("en-IN")}` : "Not answered"}</strong></div><div className="review-line"><span>Work situation</span><strong>{value("employment", "employment_status")}</strong></div><div className="review-line"><span>Farmer status</span><strong>{value("agriculture", "farmer_status")}</strong></div><div className="review-line"><span>Social category</span><strong>{value("social", "social_category")}</strong></div></div><p style={{ marginTop: 18, marginBottom: 0, fontSize: 12 }}>You can edit this profile any time. It stays in this browser and is sent to the eligibility service only when you click “See my matches”.</p></>;
}
