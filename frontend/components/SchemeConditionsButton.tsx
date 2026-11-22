"use client";

import { useEffect, useRef, useState } from "react";
import { getScheme } from "@/lib/api";
import { EligibilityReason, Scheme } from "@/lib/types";

export default function SchemeConditionsButton({ scheme, conditions = [], onAnswer }: { scheme: Scheme; conditions?: EligibilityReason[]; onAnswer?: () => void }) {
  const [open, setOpen] = useState(false);
  const [fullScheme, setFullScheme] = useState<Scheme>();
  const [loading, setLoading] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    if (!scheme.eligibility_text || !scheme.source_urls.length) {
      setLoading(true);
      getScheme(scheme.scheme_id).then((full) => { if (full) setFullScheme(full); }).finally(() => setLoading(false));
    }
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, scheme]);

  const details = fullScheme || scheme;
  const criteria = conditions.filter((condition) => condition.status !== "EXTERNAL_CHECK");
  const external = conditions.filter((condition) => condition.status === "EXTERNAL_CHECK");
  const triggerLabel = conditions.some((condition) => condition.status === "FAIL") ? "Why not eligible?" : "Conditions";
  const eligibilityPoints = (details.eligibility_text || details.application_guide?.who_should_try || "Check the official source below for the current eligibility conditions.")
    .split(/\n+|(?<=[.!?])\s+|;\s*/).map((point) => point.replace(/^[-•\s]+/, "").trim()).filter(Boolean);
  const exclusionPoints = (details.exclusions_text || "").split(/\n+|(?<=[.!?])\s+|;\s*/).map((point) => point.replace(/^[-•\s]+/, "").trim()).filter(Boolean);
  const sourceUrls = [...new Set([...conditions.map((condition) => condition.source_url || ""), ...(details.source_urls || [])].filter(Boolean))];
  const answerFromConditions = () => { setOpen(false); onAnswer?.(); };
  return <>
    <button className="conditions-trigger" type="button" onClick={() => setOpen(true)} aria-label={`${triggerLabel} for ${scheme.name}`}><svg aria-hidden="true" viewBox="0 0 20 20" width="15" height="15" fill="none"><circle cx="10" cy="10" r="7.4" stroke="currentColor" strokeWidth="1.5"/><path d="M8.35 7.45a1.75 1.75 0 1 1 2.8 1.4c-.75.52-1.15.9-1.15 1.8M10 13.45v.1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>{triggerLabel}</button>
    {open && <div className="conditions-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}><section className="conditions-dialog" role="dialog" aria-modal="true" aria-labelledby="conditions-title"><div className="conditions-dialog-head"><div><span className="eyebrow">Eligibility guide</span><h2 id="conditions-title">{scheme.name}</h2></div><button ref={closeRef} type="button" className="conditions-close" onClick={() => setOpen(false)} aria-label="Close conditions">×</button></div><p className="conditions-intro">Review these conditions before applying. Scheme authorities verify the final eligibility and supporting records.</p>
      {loading && !details.eligibility_text && <p className="conditions-loading">Loading the scheme’s eligibility information…</p>}
      {criteria.length > 0 ? <section className="conditions-block"><h3>Conditions used for this match</h3><ConditionList items={criteria} onAnswer={answerFromConditions}/></section> : <section className="conditions-block"><h3>Eligibility conditions</h3><PlainConditionList items={eligibilityPoints}/></section>}
      {criteria.length > 0 && eligibilityPoints.length > 0 && <section className="conditions-block"><h3>Other eligibility details</h3><PlainConditionList items={eligibilityPoints}/></section>}
      {exclusionPoints.length > 0 && <section className="conditions-block"><h3>Common exclusions</h3><PlainConditionList items={exclusionPoints}/></section>}
      {external.length > 0 && <section className="conditions-block"><h3>Needs official confirmation</h3><ConditionList items={external}/></section>}
      <div className="conditions-dialog-actions">{sourceUrls.map((source, index) => <a className="btn btn-secondary btn-small" href={source} target="_blank" rel="noreferrer" key={source}>{index === 0 ? "Official eligibility source" : "Other scheme source"} ↗</a>)}{details.application_url && <a className="btn btn-primary btn-small" href={details.application_url} target="_blank" rel="noreferrer">Application route ↗</a>}</div>
    </section></div>}
  </>;
}

function PlainConditionList({ items }: { items: string[] }) {
  return <ul className="condition-plain-list">{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>;
}

function ConditionList({ items, onAnswer }: { items: EligibilityReason[]; onAnswer?: () => void }) {
  const statusMeta = {
    PASS: { icon: "✓", label: "Matches", className: "condition-pass" },
    FAIL: { icon: "×", label: "Does not match", className: "condition-fail" },
    UNKNOWN: { icon: "?", label: "Not answered", className: "condition-unknown" },
    EXTERNAL_CHECK: { icon: "↗", label: "Verify", className: "condition-external" },
  } as const;
  return <ul className="condition-status-list">{items.map((item, index) => {
    const meta = statusMeta[item.status || "UNKNOWN"];
    return <li className={`condition-status-row ${meta.className}`} key={`${item.label || item.message}-${index}`}><span className="condition-status-icon" aria-hidden="true">{meta.icon}</span><span className="condition-status-copy"><strong>{meta.label}</strong><span>{item.message}</span></span>{item.status === "UNKNOWN" && item.label && onAnswer && <button className="reason-action" type="button" onClick={onAnswer}>Answer</button>}</li>;
  })}</ul>;
}
