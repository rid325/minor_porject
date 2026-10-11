import Link from "next/link";
import { Scheme } from "@/lib/types";

function readinessMeta(readiness: Scheme["application_readiness"]) {
  if (readiness === "YES") return { label: "Ready to explore", className: "status-ready" };
  if (readiness === "CONDITIONAL") return { label: "Check one caution", className: "status-caution" };
  if (readiness === "NO") return { label: "Research incomplete", className: "status-incomplete" };
  return { label: "Route to confirm", className: "status-unknown" };
}

export function SchemeStatus({ readiness }: { readiness: Scheme["application_readiness"] }) {
  const meta = readinessMeta(readiness);
  return <span className={`status-chip ${meta.className}`}>{meta.label}</span>;
}

export function SchemeCard({ scheme }: { scheme: Scheme }) {
  return (
    <article className="scheme-card">
      <div className="scheme-card-top">
        <span className="category">{scheme.category}</span>
        <SchemeStatus readiness={scheme.application_readiness} />
      </div>
      <h3><Link href={`/schemes/${encodeURIComponent(scheme.scheme_id)}`}>{scheme.name}</Link></h3>
      <p className="scheme-summary">{scheme.summary || scheme.benefit}</p>
      <div className="scheme-card-bottom">
        <span className="scheme-location"><span aria-hidden="true">⌖</span> {scheme.jurisdiction}</span>
        <Link className="btn btn-secondary btn-small" href={`/schemes/${encodeURIComponent(scheme.scheme_id)}`}>View details <span aria-hidden="true">→</span></Link>
      </div>
    </article>
  );
}
