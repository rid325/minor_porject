"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { documentRequest, type DocumentKind } from "@/lib/documents";

type ComparedDocument = { kind: string; label: string; value: string; displayValue?: string; page: number; number: number; confidence?: number | null };
type Route = {
  title: string;
  online_offline: string;
  where: string;
  mandatory: string[];
  conditional: string[];
  steps: string[];
  fees_timing: string;
  sources: [string, string][];
};
export type Guide = {
  mode: "ai_assisted" | "official_guidance";
  retryable: boolean;
  ai_requested: boolean;
  difference_in_days: number | null;
  profile_display_value?: string | null;
  explanation: string;
  priority?: string;
  possible_reasons?: string[];
  impact: string;
  first_action: string;
  correction: string;
  why: string;
  routes: Route[];
  follow_ups: string[];
  next_steps: string[];
};

export default function MismatchResolution({ schemeId, field, fieldLabel, pair, onGuide }: {
  schemeId?: string;
  field: string;
  fieldLabel: string;
  pair: [ComparedDocument, ComparedDocument];
  onGuide?: (guide: Guide) => void;
}) {
  const [open, setOpen] = useState(false);
  const [catalogue, setCatalogue] = useState<Record<string, DocumentKind>>({});
  const [guide, setGuide] = useState<Guide>();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [catalogueError, setCatalogueError] = useState(false);
  const [catalogueAttempt, setCatalogueAttempt] = useState(0);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    documentRequest<Record<string, DocumentKind>>("/document-types", { signal: controller.signal })
      .then(setCatalogue)
      .catch(() => { if (!controller.signal.aborted) setCatalogueError(true); });
    return () => controller.abort();
  }, [open, catalogueAttempt]);

  function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const submitter = (event.nativeEvent as SubmitEvent).submitter;
    void requestGuide(pair.map((item, index) => String(form.get("kind-" + index) ?? item.kind)),
      String(form.get("verified-record") ?? "unknown"),
      submitter instanceof HTMLButtonElement && submitter.value === "gemini", form.has("share-values"));
  }

  async function requestGuide(kinds: string[], verifiedRecord: string, useGemini: boolean, shareValues = false) {
    setPending(true);
    setGuide(undefined);
    setError("");
    try {
      const result = await documentRequest<Guide>((schemeId ? "/schemes/" + encodeURIComponent(schemeId) : "") + "/document-resolutions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          field,
          documents: pair.map((item, index) => ({ kind: kinds[index], value: item.value, ocr_confidence: item.confidence })),
          verified_record: verifiedRecord,
          ai_consent: useGemini,
          share_conflicting_values: useGemini && shareValues,
        }),
      });
      setGuide(result);
      onGuide?.(result);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "The guide could not be generated. Try again.");
    } finally {
      setPending(false);
    }
  }

  const groups = Object.entries(catalogue).reduce<Record<string, [string, DocumentKind][]>>((result, item) => {
    (result[item[1].category] ??= []).push(item);
    return result;
  }, {});
  return (
    <section className="mismatch-resolution">
      <button type="button" className="btn btn-secondary" aria-expanded={open} onClick={() => {
        setOpen(!open);
        if (!open && !guide && !pending) void requestGuide(pair.map((item) => item.kind), "unknown", true);
      }}>
        {open ? "Close correction guide" : "How to rectify with Gemini"}
      </button>
      {!open && <small className="checker-ai-privacy">Gemini uses document types and mismatch context. Sharing exact values is optional.</small>}
      {open && (
        <div className="mismatch-resolution-content">
          <h4>Mismatch Detected</h4>
          <p>{fieldLabel}</p>
          <dl className="resolution-values">
            {pair.map((item) => <div key={item.number}>
              <dt>{item.number ? <>Document {item.number} · {item.label} · Page {item.page}</> : item.label}</dt>
              <dd>{item.number ? item.displayValue ?? item.value : guide?.profile_display_value ?? (pending ? "Loading profile value…" : "See your saved profile")}</dd>
            </div>)}
          </dl>
          <form onSubmit={generate} onChange={() => setGuide(undefined)}>
            <fieldset disabled={pending}>
              {pair.map((item, index) => item.number === 0 ? (
                <input key={item.kind} type="hidden" name={"kind-" + index} value={item.kind} />
              ) : (
                <label key={item.number}>Document {item.number} type
                  <select name={"kind-" + index} defaultValue={item.kind}>
                    <option value={item.kind}>{item.label}</option>
                    {Object.entries(groups).map(([category, entries]) => (
                      <optgroup key={category} label={category}>
                        {entries.filter(([code]) => code !== item.kind).map(([code, entry]) => <option key={code} value={code}>{entry.label}</option>)}
                      </optgroup>
                    ))}
                  </select>
                </label>
              ))}
              {catalogueError && <p role="status">The exact document types could not be loaded. <button type="button" className="btn btn-ghost" onClick={() => { setCatalogueError(false); setCatalogueAttempt((attempt) => attempt + 1); }}>Retry</button></p>}
              <label>Has an issuer confirmed which value is correct?
                <select name="verified-record" defaultValue="unknown">
                  <option value="unknown">I’m not sure</option>
                  <option value="first">{pair[0].number ? "Document " + pair[0].number : "Saved profile"} is correct</option>
                  <option value="second">{pair[1].number ? "Document " + pair[1].number : "Saved profile"} is correct</option>
                  <option value="neither">Both values are incorrect</option>
                </select>
              </label>
              <p>Gemini uses document types, mismatch context, and location when available. File contents, document numbers, and full addresses are excluded from Gemini requests.</p>
              {["name", "father_name", "mother_name", "date_of_birth"].includes(field) && <label>
                <input type="checkbox" name="share-values" /> Include the two values shown above in my next Gemini request
              </label>}
              <div className="checker-actions">
                <button type="submit" value="gemini" className="btn btn-primary">{pending ? "Preparing guide…" : "Get Gemini suggestions"}</button>
                <button type="submit" value="official" className="btn btn-secondary">View official guide</button>
              </div>
            </fieldset>
          </form>
          {pending && <p role="status">Preparing the correction guide…</p>}
          {error && <p role="alert">{error}</p>}
          {guide && (
            <ResolutionGuide guide={guide} />
          )}
        </div>
      )}
    </section>
  );
}

export function ResolutionGuide({ guide }: { guide: Guide }) {
  const officialLinks = [...new Map(guide.routes.flatMap((route) => route.sources)
    .map(([label, url]) => [url, label])).entries()];
  const sections: { title: string; render: (route: Route) => ReactNode }[] = [
    { title: "Online / Offline Correction", render: (route) => <p>{route.online_offline}</p> },
    { title: "Where to Visit", render: (route) => <p>{route.where}</p> },
    { title: "Documents Required", render: (route) => <>
      <h5>Mandatory</h5>
      {route.mandatory.length ? <ul>{route.mandatory.map((item) => <li key={item}>{item}</li>)}</ul>
        : <p>Confirm the required documents with the issuing authority.</p>}
      {route.conditional.length > 0 && <><h5>Depending on your case</h5>
        <ul>{route.conditional.map((item) => <li key={item}>{item}</li>)}</ul></>}
    </> },
    { title: "Step-by-Step Procedure", render: (route) => <ol>{route.steps.map((item) => <li key={item}>{item}</li>)}</ol> },
    { title: "Estimated Fees and Processing Time", render: (route) => <p>{route.fees_timing}</p> },
  ];

  return (
    <div aria-live="polite" className="resolution-guide">
      <div className="resolution-recommendation">
        <h4>{guide.mode === "ai_assisted" ? "AI Recommendation" : "Recommended First Action"}</h4>
        <p><strong>{guide.first_action}</strong></p>
        {guide.priority && <p>Correction priority: {guide.priority}</p>}
        <p>{guide.explanation}</p>
      </div>
      <section className="resolution-report-section">
        <h4>Why the Mismatch Matters</h4>
        {guide.difference_in_days !== null && <p>The dates differ by {guide.difference_in_days} {guide.difference_in_days === 1 ? "day" : "days"}.</p>}
        <p>{guide.impact}</p>
        {Boolean(guide.possible_reasons?.length) && <>
          <h5>Possible reasons</h5>
          <ul>{guide.possible_reasons?.map((reason) => <li key={reason}>{reason}</li>)}</ul>
        </>}
        {guide.ai_requested && guide.mode === "official_guidance" && !guide.retryable && <p role="status">AI personalization is unavailable in this deployment. The official guidance is below.</p>}
        {guide.retryable && <p role="status">AI personalization is unavailable right now. You can use the guidance below or retry.</p>}
      </section>
      <h4>Which Document Should Be Corrected?</h4>
      <p>{guide.correction}</p>
      <h4>Why This Document?</h4>
      <p>{guide.why}</p>
      {sections.map((section) => (
        <details key={section.title} className="resolution-route">
          <summary>{section.title}</summary>
          {guide.routes.map((route, index) => (
            <div key={index} className="resolution-report-section">
              <h5>{route.title}</h5>
              <small>{route.sources.length ? "Official sources" : "General guidance"}</small>
              {section.render(route)}
            </div>
          ))}
        </details>
      ))}
      <h4>Official Government Links</h4>
      {officialLinks.length > 0 ? (
        <ul>{officialLinks.map(([url, label]) => <li key={url}><a href={url} target="_blank" rel="noreferrer">{label}</a></li>)}</ul>
      ) : <p>Ask the issuing authority for its official correction page.</p>}
      <h4>Your Next Steps</h4>
      {guide.follow_ups.length > 0 && <div className="resolution-review-note">
        <strong>Confirm before requesting a correction</strong>
        <ul>{guide.follow_ups.map((item) => <li key={item}>{item}</li>)}</ul>
      </div>}
      <ol>{guide.next_steps.map((item) => <li key={item}>{item}</li>)}</ol>
    </div>
  );
}









