"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getScheme } from "@/lib/api";
import { Scheme } from "@/lib/types";
import { SchemeStatus } from "./SchemeCard";

export default function SchemeDetail({ id }: { id: string }) {
  const [scheme, setScheme] = useState<Scheme>();
  const [loading, setLoading] = useState(true);
  useEffect(() => { getScheme(id).then(setScheme).finally(() => setLoading(false)); }, [id]);
  if (loading) return <main className="page-wrap"><div className="loading" style={{ minHeight: 500 }}>Loading scheme details…</div></main>;
  if (!scheme) return <main className="page-wrap"><div className="page-intro"><span className="eyebrow">Scheme not found</span><h1>That record is not available.</h1><p>Try returning to the catalogue and choosing another scheme.</p><Link className="btn btn-primary" href="/schemes" style={{ marginTop: 22 }}>Back to catalogue</Link></div></main>;
  return (
    <main>
      <div className="page-wrap page-intro"><Link href="/schemes" className="eyebrow">← Back to catalogue</Link><h1>{scheme.name}</h1><p>{scheme.summary || scheme.benefit}</p><div className="detail-meta"><SchemeStatus readiness={scheme.application_readiness} /><span className="meta-pill">{scheme.jurisdiction}</span><span className="meta-pill">{scheme.category}</span>{scheme.last_checked && <span className="meta-pill">Checked {formatDate(scheme.last_checked)}</span>}</div></div>
      <div className="page-wrap detail-layout">
        <div className="detail-main">
          <DetailCard title="What you could receive"><p>{scheme.benefit || "Benefit details are being confirmed with the administering department."}</p></DetailCard>
          <DetailCard title="Who should look at this"><p>{scheme.eligibility_text || "Eligibility information has not yet been structured for this record."}</p>{scheme.exclusions_text && <><h3 style={{ marginTop: 22 }}>Common exclusions</h3><p>{scheme.exclusions_text}</p></>}</DetailCard>
          <DetailCard title="What to keep ready"><p>{scheme.documents_text || "Check the official route for the current document list."}</p></DetailCard>
          {scheme.application_steps && <DetailCard title="A simple route through the process"><ol>{steps(scheme.application_steps).map((step) => <li key={step}>{step}</li>)}</ol></DetailCard>}
          {scheme.tracking_method && <DetailCard title="Tracking and support"><p>{scheme.tracking_method}</p></DetailCard>}
          {scheme.source_urls.length > 0 && <DetailCard title="Sources"><p style={{ marginTop: 0 }}>Use the official source to verify current rules before applying{scheme.source_authority ? ` · ${scheme.source_authority}` : ""}.</p><ul className="source-list">{scheme.source_urls.map((source) => <li key={source}><a href={source} target="_blank" rel="noreferrer">{source} <span aria-hidden="true">↗</span></a></li>)}</ul></DetailCard>}
        </div>
        <aside className="detail-side side-sticky">
          <div className="detail-card apply-card"><h2>Application route</h2><p>Use the official route to confirm current eligibility, documents, deadlines and submission requirements.</p>{scheme.application_url ? <><a className="btn btn-primary apply-link" href={scheme.application_url} target="_blank" rel="noreferrer">Open official application route <span aria-hidden="true">↗</span></a>{scheme.application_mode && <p className="route-note">{scheme.application_mode}</p>}<p className="route-disclaimer">The link may require login, assisted service-centre support or departmental verification. Nagrik Path does not submit an application on your behalf.</p></> : <p style={{ marginBottom: 0 }}>No verified online route is currently recorded. Contact the administering department or a nearby service centre.</p>}</div>
          {scheme.important_caution && <div className="detail-card caution"><h3>One thing to confirm</h3><p>{scheme.important_caution}</p></div>}
          <div className="detail-card"><h3>Research status</h3><p>{scheme.research_status || "Research record"}</p><p style={{ fontSize: 11, marginTop: 13 }}>Application readiness is separate from personal eligibility. A “ready” route still needs document verification.</p></div>
        </aside>
      </div>
    </main>
  );
}

function DetailCard({ title, children }: { title: string; children: React.ReactNode }) { return <section className="detail-card"><h2>{title}</h2>{children}</section>; }
function steps(value: string) { return value.split(/(?=\d+[)\.])/).map((item) => item.replace(/^\s*\d+[)\.]\s*/, "").trim()).filter(Boolean); }
function formatDate(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" }).format(date); }
