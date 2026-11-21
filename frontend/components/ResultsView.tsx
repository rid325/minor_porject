"use client";

import Link from "next/link";
import { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import { checkEligibility } from "@/lib/api";
import { AccountProfile, getAccountProfile, getAuthStatus, saveAccountProfile } from "@/lib/auth";
import { clearLocalProfileData, mergeProfile, profileAnswerCount, PROFILE_OWNER_KEY, PROFILE_STORAGE_KEY, RESULTS_STORAGE_KEY } from "@/lib/profile";
import { EligibilityResponse, EligibilityReason, EligibilityResult, Profile, ResultBucket } from "@/lib/types";
import SchemeConditionsButton from "./SchemeConditionsButton";

const buckets: { key: ResultBucket; title: string; className: string }[] = [
  { key: "likely_eligible", title: "Likely eligible to explore", className: "count-green" },
  { key: "needs_information", title: "Needs more information", className: "count-yellow" },
  { key: "likely_not_eligible", title: "Not eligible", className: "count-red" },
  { key: "information_only", title: "Eligibility details", className: "count-blue" },
];
const resultPriority: Record<ResultBucket, number> = {
  likely_eligible: 0,
  needs_information: 1,
  information_only: 2,
  likely_not_eligible: 3,
};

export default function ResultsView() {
  const [response, setResponse] = useState<EligibilityResponse>();
  const [profile, setProfile] = useState<Profile>();
  const [signedIn, setSignedIn] = useState(false);
  const [accountEmail, setAccountEmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [saveMessage, setSaveMessage] = useState("");
  const [search, setSearch] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [category, setCategory] = useState("");
  const [applicantState, setApplicantState] = useState("");
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    let active = true;
    async function loadResults() {
      let cached: EligibilityResponse | undefined;
      let savedProfile: Profile | undefined;
      try {
        const resultText = window.localStorage.getItem(RESULTS_STORAGE_KEY);
        if (resultText) cached = JSON.parse(resultText);
        const profileText = window.localStorage.getItem(PROFILE_STORAGE_KEY);
        if (profileText) savedProfile = mergeProfile(JSON.parse(profileText));
      } catch { /* Continue with the account copy or the empty state. */ }
      if (cached && active) setResponse(cached);

      const auth = await getAuthStatus().catch(() => null);
      if (!active) return;
      if (auth?.authenticated) {
        setSignedIn(true);
        setAccountEmail(auth.user?.email || "");
        const localOwner = window.localStorage.getItem(PROFILE_OWNER_KEY);
        if (localOwner && localOwner !== auth.user?.email) savedProfile = undefined;
        try {
          const account: AccountProfile = await getAccountProfile();
          if (account.profile) { savedProfile = mergeProfile(account.profile); if (auth.user?.email) window.localStorage.setItem(PROFILE_OWNER_KEY, auth.user.email); }
        } catch { /* Use the local copy while the account API is unavailable. */ }
      } else {
        clearLocalProfileData();
        savedProfile = undefined;
        cached = undefined;
        setResponse(undefined);
      }
      if (!active) return;
      if (savedProfile) {
        setProfile(savedProfile);
        setApplicantState(savedProfile.location.state.trim());
        if (profileAnswerCount(savedProfile) > 0) {
          try {
            if (auth?.authenticated) {
              await saveAccountProfile(savedProfile).then(() => { if (auth.user?.email) window.localStorage.setItem(PROFILE_OWNER_KEY, auth.user.email); }).catch(() => undefined);
            }
            const fresh = await checkEligibility(savedProfile);
            if (!active) return;
            setResponse(fresh);
            window.localStorage.setItem(RESULTS_STORAGE_KEY, JSON.stringify(fresh));
            window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(savedProfile));
          } catch { /* Keep the last saved assessment if a fresh check cannot finish. */ }
        }
      }
      if (active) setLoading(false);
    }
    loadResults();
    return () => { active = false; };
  }, []);

  const allResults = useMemo(() => [...(response?.results || [])].sort((a, b) => {
    const categoryOrder = resultPriority[a.result] - resultPriority[b.result];
    if (categoryOrder) return categoryOrder;
    const aMatched = a.matched_conditions ?? a.passed?.length ?? 0;
    const bMatched = b.matched_conditions ?? b.passed?.length ?? 0;
    const aTotal = a.total_conditions ?? 0;
    const bTotal = b.total_conditions ?? 0;
    const aRate = aTotal ? aMatched / aTotal : 0;
    const bRate = bTotal ? bMatched / bTotal : 0;
    return bRate - aRate || bMatched - aMatched || a.scheme.name.localeCompare(b.scheme.name);
  }), [response]);
  const jurisdictions = useMemo(() => [...new Set(allResults.map((result) => result.scheme.jurisdiction).filter(Boolean))].sort(), [allResults]);
  const categories = useMemo(() => [...new Set(allResults.map((result) => result.scheme.category).filter(Boolean))].sort(), [allResults]);
  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return allResults.filter(({ scheme }) =>
      (!needle || `${scheme.name} ${scheme.summary} ${scheme.category} ${scheme.jurisdiction}`.toLowerCase().includes(needle))
      && (!applicantState || showAll || scheme.jurisdiction.toLowerCase() === "india" || scheme.jurisdiction.toLowerCase().includes(applicantState.toLowerCase()))
      && (!jurisdiction || scheme.jurisdiction === jurisdiction)
      && (!category || scheme.category === category));
  }, [allResults, search, jurisdiction, category, applicantState, showAll]);

  async function addSchemeAnswers(schemeId: string, answers: Record<string, string>) {
    if (!profile) return false;
    const updated: Profile = {
      ...profile,
      scheme_answers: {
        ...profile.scheme_answers,
        [schemeId]: { ...(profile.scheme_answers[schemeId] || {}), ...answers },
      },
    };
    setProfile(updated);
    setSaveMessage("Saving your answers…");
    window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(updated));
    try {
      if (signedIn) await saveAccountProfile(updated).then(() => { if (accountEmail) window.localStorage.setItem(PROFILE_OWNER_KEY, accountEmail); });
      const fresh = await checkEligibility(updated);
      setResponse(fresh);
      window.localStorage.setItem(RESULTS_STORAGE_KEY, JSON.stringify(fresh));
      setSaveMessage(signedIn ? "Answers saved to your account and matches updated." : "Answers saved in this browser and matches updated.");
      return true;
    } catch {
      setSaveMessage("We could not update matches right now. Please try again.");
      return false;
    }
  }

  if (loading) return <main className="page-wrap"><div className="loading" style={{ minHeight: 440 }}>Loading your saved personalised schemes…</div></main>;
  if (!response) return <main className="page-wrap page-intro"><span className="eyebrow">Personalised schemes</span><h1>Start with a few<br /><span style={{ color: "var(--brand)" }}>useful answers.</span></h1><p>Save a few common details once. We’ll use them to rank schemes and ask for extra details only when a particular scheme needs them.</p><Link className="btn btn-primary" href="/profile" style={{ marginTop: 22 }}>Add my common information <span aria-hidden="true">→</span></Link></main>;

  const total = response.results.length;
  return <main><div className="page-wrap page-intro"><span className="eyebrow">Personalised schemes</span><h1>Your matches,<br /><span style={{ color: "var(--brand)" }}>ranked by fit.</span></h1><p>We sort by condition matches when structured criteria are available. Add scheme-specific details when asked; we’ll save those too.</p><div className="hero-actions"><Link className="btn btn-secondary" href="/profile">Edit my common information <span aria-hidden="true">↗</span></Link><Link className="btn btn-ghost" href="/schemes">Browse all schemes <span aria-hidden="true">↗</span></Link><span className="meta-pill" style={{ alignSelf: "center" }}>{total} schemes assessed</span></div></div><div className="page-wrap"><div className="results-summary"><div className="results-intro"><h2>How matches work</h2><p>Cards with a condition count were compared with your saved answers. A <strong>?</strong> means a condition needs an answer. Choose “Add answer” to save that detail for this scheme; if unsure, choose “I don’t know” or leave it blank. Some schemes show “Eligibility details” because their conditions are presented in the scheme information instead of a personalised score; use the Conditions button to read them.</p></div><div className="results-counts">{buckets.map((bucket) => <div className={`result-count-card ${bucket.className}`} key={bucket.key}><strong>{allResults.filter((result) => result.result === bucket.key).length}</strong><span>{bucket.title}</span></div>)}</div></div>
    {saveMessage && <p className="account-inline-status" role="status">{saveMessage}</p>}
    <section className="personal-results" aria-label="Filter personalised schemes">{applicantState && <div className="state-scope"><div><strong>{showAll ? "Showing all assessed schemes" : `Showing schemes for ${applicantState}`}</strong><span>{showAll ? "State and nationwide schemes are included." : `Filtered to ${applicantState} and nationwide schemes.`}</span></div><button className="btn btn-primary state-scope-toggle" type="button" onClick={() => setShowAll((value) => !value)}>{showAll ? `Show ${applicantState} schemes` : "Show all schemes"}</button></div>}<div className="catalogue-top"><label className="sr-only" htmlFor="personal-search">Search matched schemes</label><input className="field" id="personal-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by scheme, benefit or sector…"/><span className="result-count">{filtered.length} of {total} schemes</span></div><div className="personal-filters"><label><span className="filter-label">Jurisdiction</span><select className="select" value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)}><option value="">All jurisdictions</option>{jurisdictions.map((item) => <option key={item}>{item}</option>)}</select></label><label><span className="filter-label">Sector</span><select className="select" value={category} onChange={(event) => setCategory(event.target.value)}><option value="">All sectors</option>{categories.map((item) => <option key={item}>{item}</option>)}</select></label></div>
    {filtered.length ? <div className="result-list">{filtered.map((result) => <ResultRow result={result} profile={profile} onSaveAnswers={addSchemeAnswers} key={result.scheme.scheme_id}/>)}</div> : <div className="empty-state">No schemes match those filters. Try clearing a filter or broadening your search.</div>}</section></div></main>;
}

function ResultRow({ result, profile, onSaveAnswers }: { result: EligibilityResult; profile?: Profile; onSaveAnswers: (schemeId: string, answers: Record<string, string>) => Promise<boolean> }) {
  const [answersOpen, setAnswersOpen] = useState(false);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const reasons = [...(result.reasons || []), ...(result.passed || []), ...(result.failed || []), ...(result.unknown || []), ...(result.external_checks || [])].filter((reason, index, list) => list.findIndex((candidate) => candidate.message === reason.message) === index);
  const unknownReasons = reasons.filter((reason) => reason.status === "UNKNOWN" && reason.label);
  const visibleReasons = result.result === "likely_not_eligible"
    ? reasons.filter((reason) => reason.status === "FAIL")
    : reasons.filter((reason) => reason.status !== "UNKNOWN");
  const matched = result.matched_conditions ?? result.passed?.length ?? 0;
  const total = result.total_conditions ?? 0;
  const bucketLabel = buckets.find((bucket) => bucket.key === result.result)?.title || "Needs more information";
  const showAnswers = () => {
    setAnswers(Object.fromEntries(unknownReasons.map((reason) => [reason.label!, profile?.scheme_answers?.[result.scheme.scheme_id]?.[reason.label!] || ""])));
    setAnswersOpen(true);
    setError("");
  };
  async function submitAnswer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const completedAnswers = Object.fromEntries(Object.entries(answers).filter(([, value]) => value.trim()));
    if (!Object.keys(completedAnswers).length) { setError("Answer at least one condition before saving."); return; }
    setSaving(true); setError("");
    const ok = await onSaveAnswers(result.scheme.scheme_id, completedAnswers);
    setSaving(false);
    if (ok) setAnswersOpen(false);
    else setError("We could not save that answer. Please try again.");
  }
  const notAssessed = result.result === "information_only";
  const conditionBadge = notAssessed ? "Eligibility not assessed" : `${matched} of ${total} conditions match`;
  const displayedStatus = bucketLabel;
  return <article className="result-row"><div className="result-row-top"><div><h3>{result.scheme.name}</h3><div className="result-row-meta">{result.scheme.jurisdiction} · {result.scheme.category}</div></div><div className="result-badges"><span className={`match-count ${notAssessed ? "match-details" : ""}`}>{conditionBadge}</span>{!notAssessed && <span className={`match-count match-status ${result.result === "likely_not_eligible" ? "match-ineligible" : ""}`}>{displayedStatus}</span>}</div></div>{unknownReasons.length > 0 && <div className="missing-info-summary"><span><strong aria-hidden="true">?</strong> {unknownReasons.length} {unknownReasons.length === 1 ? "condition needs" : "conditions need"} your information</span><button className="reason-action" type="button" onClick={showAnswers}>View and answer all</button></div>}{visibleReasons.length > 0 && <div className="reason-list">{visibleReasons.map((reason, index) => <Reason reason={reason} onAddAnswer={showAnswers} key={`${reason.message}-${index}`}/>)}</div>}{answersOpen && <form className="scheme-answer-form scheme-answer-list" onSubmit={submitAnswer}><div><strong>Answer scheme conditions</strong><span>Your answers are saved to your profile and used to update this match.</span></div>{unknownReasons.map((reason) => <label className="scheme-answer-item" key={reason.label}><span>{reason.message}</span><AnswerInput field={reason.label || ""} value={answers[reason.label || ""] || ""} onChange={(value) => setAnswers((current) => ({ ...current, [reason.label || ""]: value }))}/></label>)}{error && <span className="scheme-answer-error" role="alert">{error}</span>}<div className="scheme-answer-actions"><button className="btn btn-primary btn-small" type="submit" disabled={saving}>{saving ? "Saving…" : "Save answers and update matches"}</button><button className="btn btn-ghost btn-small" type="button" onClick={() => setAnswersOpen(false)}>Cancel</button></div></form>}<div className="result-row-actions"><SchemeConditionsButton scheme={result.scheme} conditions={reasons} onAnswer={showAnswers}/><Link className="btn btn-secondary btn-small" href={`/schemes/${encodeURIComponent(result.scheme.scheme_id)}`}>Scheme information <span aria-hidden="true">→</span></Link>{result.scheme.application_url && <a className="btn btn-ghost btn-small" href={result.scheme.application_url} target="_blank" rel="noreferrer">Official route ↗</a>}</div></article>;
}

function AnswerInput({ field, value, onChange }: { field: string; value: string; onChange: (value: string) => void }) {
  const yesNoFields = ["personal.is_widow", "personal.is_orphan", "personal.pm_kisan_constitutional_post_family", "personal.pm_kisan_elected_official_family", "household.is_bpl", "household.has_lpg_connection", "household.pm_kisan_pension_10000_family", "household.pm_kisan_income_tax_payer_family", "household.receives_government_pension", "employment.unorganised_worker", "employment.income_tax_payer", "employment.epfo_member", "employment.esic_member", "employment.pm_kisan_non_exempt_government_employee_family", "employment.pm_kisan_practicing_professional_family", "agriculture.farmer_status", "agriculture.pm_kisan_institutional_landholder", "agriculture.insurable_crop_interest", "agriculture.crop_notified", "social.has_savings_bank_account", "social.has_bank_account", "social.has_aadhaar", "social.has_mobile", "social.residential_electricity_connection", "location.pm_kisan_nri_family"];
  if (yesNoFields.includes(field)) return <label className="form-field"><span>Your answer</span><select className="select" value={value} onChange={(event) => onChange(event.target.value)} required><option value="">Choose an answer</option><option value="yes">Yes</option><option value="no">No</option><option value="unknown">I don’t know</option></select></label>;
  if (field === "agriculture.pm_kisan_land_record_status") return <label className="form-field"><span>What does the official land record show?</span><select className="select" value={value} onChange={(event) => onChange(event.target.value)} required><option value="">Choose a record type</option><option value="single_owner">Applicant is the recorded single owner</option><option value="joint_owner">Applicant is a recorded joint owner</option><option value="inherited_and_updated">Inherited land; mutation/record is updated</option><option value="tenant_or_lease">Tenant or lease only</option><option value="cultivator_without_record">Cultivates, but is not listed as owner</option><option value="no_record">No cultivable land record</option><option value="unknown">I don’t know</option></select></label>;
  if (field === "agriculture.landholding_status") return <label className="form-field"><span>Your answer</span><select className="select" value={value} onChange={(event) => onChange(event.target.value)} required><option value="">Choose an answer</option>{["owner", "landholder", "cultivator", "tenant", "owned", "leased", "none", "unknown"].map((option) => <option key={option} value={option}>{option === "unknown" ? "I don’t know" : option.replaceAll("_", " ")}</option>)}</select></label>;
  if (field === "social.electricity_consumer_type") return <label className="form-field"><span>Your answer</span><select className="select" value={value} onChange={(event) => onChange(event.target.value)} required><option value="">Choose an answer</option><option value="residential">Residential / household</option><option value="commercial">Commercial</option><option value="unknown">I don’t know</option></select></label>;
  const numeric = field === "age" || field.includes("income") || field.includes("percentage") || field.includes("acres");
  const date = field.endsWith("date_of_birth");
  return <label className="form-field"><span>{numeric ? "Enter a number" : date ? "Select a date" : "Your answer"}</span><input className="field" type={date ? "date" : numeric ? "number" : "text"} value={value} onChange={(event) => onChange(event.target.value)} required /></label>;
}

function Reason({ reason, onAddAnswer }: { reason: EligibilityReason; onAddAnswer: (reason: EligibilityReason) => void }) {
  const className = reason.status === "PASS" ? "pass" : reason.status === "FAIL" ? "fail" : reason.status === "EXTERNAL_CHECK" ? "external" : "unknown";
  const icon = reason.status === "PASS" ? "✓" : reason.status === "FAIL" ? "×" : reason.status === "EXTERNAL_CHECK" ? "↗" : "?";
  return <span className={`reason ${className}`}><strong aria-hidden="true">{icon}</strong><span>{reason.status === "UNKNOWN" && <strong className="reason-label">Information needed: </strong>}{reason.message}</span>{reason.status === "UNKNOWN" && reason.label && <button className="reason-action" type="button" onClick={() => onAddAnswer(reason)}>Add answer</button>}</span>;
}
