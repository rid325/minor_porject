"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { RESULTS_STORAGE_KEY } from "@/lib/profile";
import { EligibilityResponse, EligibilityReason, EligibilityResult, ResultBucket } from "@/lib/types";
import { SchemeStatus } from "./SchemeCard";

const buckets: { key: ResultBucket; title: string; description: string; className: string }[] = [
  { key: "likely_eligible", title: "Likely eligible to explore", description: "No reviewed condition has ruled these out yet. Verify the details before applying.", className: "count-green" },
  { key: "needs_information", title: "Needs more information", description: "A missing answer or unresolved condition is keeping these from a confident result.", className: "count-yellow" },
  { key: "likely_not_eligible", title: "Likely not eligible", description: "A known condition appears not to match. We show the reason so you can double-check it.", className: "count-red" },
  { key: "information_only", title: "Information only", description: "The catalogue record still needs a reviewed rule or usable route.", className: "count-blue" },
];

export default function ResultsView() {
  const [response, setResponse] = useState<EligibilityResponse>();
  useEffect(() => { try { const value = window.localStorage.getItem(RESULTS_STORAGE_KEY); if (value) setResponse(JSON.parse(value)); } catch { /* ignore */ } }, []);
  const grouped = useMemo(() => Object.fromEntries(buckets.map((bucket) => [bucket.key, response?.results.filter((result) => result.result === bucket.key) || []])) as Record<ResultBucket, EligibilityResult[]>, [response]);
  if (!response) return <main className="page-wrap page-intro"><span className="eyebrow">Your results</span><h1>Start with a few<br /><span style={{ color: "var(--brand)" }}>useful answers.</span></h1><p>Once you have completed your profile, we will group every scheme into clear next steps.</p><Link className="btn btn-primary" href="/profile" style={{ marginTop: 22 }}>Build my profile <span aria-hidden="true">→</span></Link></main>;
  const total = response.results.length;
  return <main><div className="page-wrap page-intro"><span className="eyebrow">Your results</span><h1>A shortlist with<br /><span style={{ color: "var(--brand)" }}>the why included.</span></h1><p>These are pre-screening signals based on the information you entered. Check the explanation and the official route before making a decision.</p><div className="hero-actions"><Link className="btn btn-secondary" href="/profile">Edit my profile <span aria-hidden="true">↗</span></Link><span className="meta-pill" style={{ alignSelf: "center" }}>{total} schemes checked · {response.rule_set_version || "reviewed rules"}</span></div></div><div className="page-wrap"><div className="results-summary"><div className="results-intro"><h2>What this means</h2><p>“Likely eligible” means the reviewed conditions currently fit what you told us. It is not a guarantee of approval, funding or a place on a beneficiary list.</p></div><div className="results-counts">{buckets.map((bucket) => <div className={`result-count-card ${bucket.className}`} key={bucket.key}><strong>{grouped[bucket.key].length}</strong><span>{bucket.title}</span></div>)}</div></div>{buckets.map((bucket) => <ResultSection bucket={bucket} results={grouped[bucket.key]} key={bucket.key} />)}</div></main>;
}

function ResultSection({ bucket, results }: { bucket: typeof buckets[number]; results: EligibilityResult[] }) {
  return <section className="page-wrap result-section"><div className="result-section-head"><h2>{bucket.title}</h2><span>{bucket.description}</span></div>{results.length ? <div className="result-list">{results.map((result) => <ResultRow result={result} key={result.scheme.scheme_id} />)}</div> : <div className="empty-state" style={{ padding: "25px 20px", textAlign: "left" }}>No schemes in this group yet.</div>}</section>;
}

function ResultRow({ result }: { result: EligibilityResult }) {
  const reasons = [...(result.reasons || []), ...(result.failed || []), ...(result.unknown || []), ...(result.external_checks || [])].filter((reason, index, list) => list.findIndex((candidate) => candidate.message === reason.message) === index).slice(0, 5);
  return <article className="result-row"><div className="result-row-top"><div><h3>{result.scheme.name}</h3><div className="result-row-meta">{result.scheme.jurisdiction} · {result.scheme.category}</div></div><SchemeStatus readiness={result.scheme.application_readiness} /></div>{reasons.length > 0 && <div className="reason-list">{reasons.map((reason, index) => <Reason reason={reason} key={`${reason.message}-${index}`} />)}</div>}<div className="result-row-actions"><Link className="btn btn-secondary btn-small" href={`/schemes/${encodeURIComponent(result.scheme.scheme_id)}`}>Read details <span aria-hidden="true">→</span></Link>{result.scheme.application_url && <a className="btn btn-ghost btn-small" href={result.scheme.application_url} target="_blank" rel="noreferrer">Official route ↗</a>}</div></article>;
}

function Reason({ reason }: { reason: EligibilityReason }) {
  const className = reason.status === "PASS" ? "pass" : reason.status === "FAIL" ? "fail" : reason.status === "EXTERNAL_CHECK" ? "external" : "unknown";
  const icon = reason.status === "PASS" ? "✓" : reason.status === "FAIL" ? "×" : reason.status === "EXTERNAL_CHECK" ? "↗" : "?";
  return <span className={`reason ${className}`}><strong aria-hidden="true">{icon}</strong>{reason.message}</span>;
}
