import type { Metadata } from "next";
import DocumentCheckerWorkspace from "@/components/DocumentCheckerWorkspace";

export const metadata: Metadata = { title: "Document Mismatch Checker | Yojna Connect" };

export default function DocumentCheckerPage() {
  return (
    <main className="page-wrap checker-page">
      <div className="page-intro checker-page-intro">
        <h1>Document Mismatch Checker</h1>
        <p>Find differences across documents and your saved profile. Sign in to run your check.</p>
      </div>
      <DocumentCheckerWorkspace />
    </main>
  );
}



