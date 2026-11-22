"use client";

import { useState } from "react";
import DocumentChecker from "./DocumentChecker";
import SavedDocuments from "./SavedDocuments";

export default function DocumentCheckerWorkspace() {
  const [checking, setChecking] = useState(false);

  return (
    <>
      <div className="checker-source-actions" role="group" aria-label="Document tools">
        <button type="button" className={"btn " + (checking ? "btn-secondary" : "btn-primary")}
          aria-pressed={!checking} onClick={() => setChecking(false)}>Upload document</button>
        <button type="button" className={"btn " + (checking ? "btn-primary" : "btn-secondary")}
          aria-pressed={checking} onClick={() => setChecking(true)}>Check mismatch</button>
      </div>
      {checking ? <DocumentChecker savedOnly /> : <SavedDocuments uploadOnly />}
    </>
  );
}
