import Link from "next/link";
import { Scheme } from "@/lib/types";
import SchemeConditionsButton from "./SchemeConditionsButton";

export function SchemeCard({ scheme }: { scheme: Scheme }) {
  return (
    <article className="scheme-card">
      <div className="scheme-card-top"><span className="category">{scheme.category}</span></div>
      <h3><Link href={`/schemes/${encodeURIComponent(scheme.scheme_id)}`}>{scheme.name}</Link></h3>
      <p className="scheme-summary">{scheme.summary || scheme.benefit}</p>
      <div className="scheme-card-bottom">
        <span className="scheme-location"><span aria-hidden="true">⌖</span> {scheme.jurisdiction}</span>
        <div className="scheme-card-actions"><SchemeConditionsButton scheme={scheme}/><Link className="btn btn-secondary btn-small" href={`/schemes/${encodeURIComponent(scheme.scheme_id)}`} aria-label={`View information about ${scheme.name}`}>Scheme information <span aria-hidden="true">→</span></Link></div>
      </div>
    </article>
  );
}
