"use client";

import { useEffect, useState } from "react";
import { documentRequest } from "@/lib/documents";
import { ResolutionGuide, type Guide } from "./MismatchResolution";

type Example = { documents: { label: string; value: string }[]; guide: Guide };

export default function DocumentResolutionExample({ schemeId }: { schemeId?: string }) {
  const [example, setExample] = useState<Example>();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (window.location.hash === "#mismatch-example") {
      document.getElementById("mismatch-example")?.scrollIntoView({ block: "start" });
    }
  }, []);

  async function showExample() {
    setPending(true);
    setError(false);
    try {
      setExample(await documentRequest<Example>(
        (schemeId ? "/schemes/" + encodeURIComponent(schemeId) : "") + "/document-resolution-example",
      ));
    } catch {
      setError(true);
    } finally {
      setPending(false);
    }
  }

  return (
    <div id="mismatch-example" className="mismatch-resolution">
      <h3>Try a sample mismatch</h3>
      <p>See how the guide handles two fictional dates of birth. No sign-in or upload is needed.</p>
      {!example && <button type="button" className="btn btn-secondary" onClick={showExample} disabled={pending}>
        {pending ? "Loading example…" : error ? "Retry sample guide" : "How to Fix This Mismatch?"}
      </button>}
      {error && <p role="alert">The sample guide could not load.</p>}
      {example && (
        <div className="mismatch-resolution-content">
          <h4>Mismatch detected</h4>
          <p>Date of birth</p>
          <dl className="resolution-values">
            {example.documents.map((item) => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}
          </dl>
          <ResolutionGuide guide={example.guide} />
          <button type="button" className="btn btn-secondary" onClick={() => setExample(undefined)}>Close sample guide</button>
        </div>
      )}
    </div>
  );
}


