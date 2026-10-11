"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getSchemes } from "@/lib/api";
import { Scheme } from "@/lib/types";
import { SchemeCard } from "./SchemeCard";

type Props = { limit?: number; embedded?: boolean };

export default function Catalogue({ limit, embedded = false }: Props) {
  const [schemes, setSchemes] = useState<Scheme[]>([]);
  const [search, setSearch] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [category, setCategory] = useState("");
  const [readiness, setReadiness] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getSchemes().then((data) => { if (active) setSchemes(data); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const jurisdictions = useMemo(() => unique(schemes.map((scheme) => scheme.jurisdiction).filter(Boolean)), [schemes]);
  const categories = useMemo(() => unique(schemes.map((scheme) => scheme.category).filter(Boolean)), [schemes]);
  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return schemes.filter((scheme) => {
      const corpus = `${scheme.name} ${scheme.summary} ${scheme.category} ${scheme.jurisdiction}`.toLowerCase();
      return (!needle || corpus.includes(needle)) && (!jurisdiction || scheme.jurisdiction === jurisdiction) && (!category || scheme.category === category) && (!readiness || scheme.application_readiness === readiness);
    });
  }, [schemes, search, jurisdiction, category, readiness]);
  const visible = limit ? filtered.slice(0, limit) : filtered;

  return (
    <section className={embedded ? "section embedded-catalogue" : "section"}>
      <div className="page-wrap">
        {!embedded && <div className="page-intro"><span className="eyebrow">The catalogue</span><h1>Support that starts<br />with <span>your story.</span></h1><p>Browse the schemes we have researched so far. You can explore freely, then add your details when you want a more personal pre-screen.</p></div>}
        {embedded && <div className="section-head"><div><span className="eyebrow">Browse first</span><h2>A starting point for every situation.</h2></div><Link className="btn btn-secondary" href="/schemes">See all schemes <span aria-hidden="true">→</span></Link></div>}
        {!embedded && <div className="stat-strip"><Stat value={schemes.length || "—"} label="schemes in the catalogue" /><Stat value={schemes.filter((scheme) => scheme.application_readiness === "YES").length || "—"} label="routes ready to explore" /><Stat value={schemes.filter((scheme) => scheme.application_readiness === "CONDITIONAL").length || "—"} label="routes with a caution" /><Stat value="0" label="identifiers required" /></div>}
        <div className="catalogue-layout">
          <aside className="filter-panel" aria-label="Filter schemes">
            <h3>Refine the list</h3>
            <div className="filter-group"><label className="filter-label" htmlFor="jurisdiction">Where</label><select className="select" id="jurisdiction" value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)}><option value="">All locations</option>{jurisdictions.map((item) => <option value={item} key={item}>{shortJurisdiction(item)}</option>)}</select></div>
            <div className="filter-group"><label className="filter-label" htmlFor="category">What kind</label><select className="select" id="category" value={category} onChange={(event) => setCategory(event.target.value)}><option value="">All categories</option>{categories.map((item) => <option value={item} key={item}>{item}</option>)}</select></div>
            <div className="filter-group"><label className="filter-label" htmlFor="readiness">Research status</label><select className="select" id="readiness" value={readiness} onChange={(event) => setReadiness(event.target.value)}><option value="">Any status</option><option value="YES">Ready to explore</option><option value="CONDITIONAL">Check one caution</option><option value="NO">Research incomplete</option></select></div>
          </aside>
          <div>
            <div className="catalogue-top"><label className="sr-only" htmlFor="scheme-search">Search schemes</label><input className="field" id="scheme-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by scheme, benefit, or life situation…" /><span className="result-count">{filtered.length} {filtered.length === 1 ? "scheme" : "schemes"}</span></div>
            {loading ? <div className="loading">Loading the catalogue…</div> : visible.length ? <div className="scheme-grid">{visible.map((scheme) => <SchemeCard scheme={scheme} key={scheme.scheme_id} />)}</div> : <div className="empty-state">No schemes match those filters. Try clearing one filter or searching a broader phrase.</div>}
            {limit && filtered.length > limit && <div style={{ marginTop: 17 }}><Link className="btn btn-ghost" href="/schemes">View all {filtered.length} matches <span aria-hidden="true">→</span></Link></div>}
          </div>
        </div>
      </div>
    </section>
  );
}

function unique(values: string[]) { return Array.from(new Set(values)).sort((a, b) => a.localeCompare(b)); }
function shortJurisdiction(value: string) { return value.length > 38 ? `${value.slice(0, 36)}…` : value; }
function Stat({ value, label }: { value: string | number; label: string }) { return <div className="stat-card"><strong>{value}</strong><span>{label}</span></div>; }
