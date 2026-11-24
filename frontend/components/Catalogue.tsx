"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getSchemes } from "@/lib/api";
import { getAccountProfile, getAuthStatus } from "@/lib/auth";
import { Scheme } from "@/lib/types";
import { isInProfileRegion, mergeProfile, PROFILE_OWNER_KEY, PROFILE_STORAGE_KEY } from "@/lib/profile";
import { SchemeCard } from "./SchemeCard";

type Props = { limit?: number; embedded?: boolean };

export default function Catalogue({ limit, embedded = false }: Props) {
  const [schemes, setSchemes] = useState<Scheme[]>([]);
  const [search, setSearch] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [category, setCategory] = useState("");
  const [applicantState, setApplicantState] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getSchemes().then((data) => { if (active) setSchemes(data); }).catch(() => { if (active) setLoadError(true); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    async function loadApplicantState() {
      try {
        const saved = window.localStorage.getItem(PROFILE_STORAGE_KEY);
        if (saved && active && !window.localStorage.getItem(PROFILE_OWNER_KEY)) setApplicantState(mergeProfile(JSON.parse(saved)).location.state.trim());
      } catch { /* Fall back to the account copy when local data is unavailable. */ }
      try {
        const auth = await getAuthStatus();
        if (!auth.authenticated) return;
        const account = await getAccountProfile();
        if (active && account.profile?.location.state) setApplicantState(account.profile.location.state.trim());
      } catch { /* Keep using the saved browser copy if account sync is unavailable. */ }
    }
    loadApplicantState();
    return () => { active = false; };
  }, []);

  const jurisdictions = useMemo(() => unique(schemes.map((scheme) => scheme.jurisdiction).filter(Boolean)), [schemes]);
  const categories = useMemo(() => unique(schemes.map((scheme) => scheme.category).filter(Boolean)), [schemes]);
  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return schemes.filter((scheme) => {
      const corpus = `${scheme.name} ${scheme.summary} ${scheme.category} ${scheme.jurisdiction}`.toLowerCase();
      const isStateOrNational = isInProfileRegion(scheme.jurisdiction, applicantState);
      return (!applicantState || showAll || isStateOrNational) && (!needle || corpus.includes(needle)) && (!jurisdiction || scheme.jurisdiction === jurisdiction) && (!category || scheme.category === category);
    });
  }, [schemes, search, jurisdiction, category, applicantState, showAll]);
  const visible = limit ? filtered.slice(0, limit) : filtered;

  return (
    <section className={embedded ? "section embedded-catalogue" : "section"}>
      <div className="page-wrap">
        {!embedded && <div className="page-intro"><span className="eyebrow">Scheme catalogue</span><h1>Government support,<br /><span>organised clearly.</span></h1><p>Review scheme information by jurisdiction and sector. Each record identifies the benefit, basic conditions, required documents and the official application route.</p><div className="hero-actions"><Link className="btn btn-primary feature-action" href="/results">Personalized schemes <span aria-hidden="true">→</span></Link><span className="meta-pill" style={{ alignSelf: "center" }}>Your saved answers rank matching schemes</span></div>{applicantState && <div className="state-scope"><div><strong>{showAll ? "Showing all schemes" : `Showing schemes for ${applicantState}`}</strong><span>{showAll ? "Your state and nationwide schemes are included." : `Includes ${applicantState} schemes and schemes available across India.`}</span></div><button className="btn btn-primary state-scope-toggle" type="button" onClick={() => setShowAll((value) => !value)}>{showAll ? `Show ${applicantState} schemes` : "Show all schemes"}</button></div>}</div>}
        {embedded && <div className="section-head"><div><span className="eyebrow">Scheme catalogue</span><h2>Browse available government support.</h2></div><Link className="btn btn-secondary" href="/schemes">Open full catalogue <span aria-hidden="true">→</span></Link></div>}
        <div className="catalogue-layout">
          <aside className="filter-panel" aria-label="Filter schemes">
            <h3>Filter catalogue</h3>
            <div className="filter-group"><label className="filter-label" htmlFor="jurisdiction">Jurisdiction</label><select className="select" id="jurisdiction" value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)}><option value="">All jurisdictions</option>{jurisdictions.map((item) => <option value={item} key={item}>{shortJurisdiction(item)}</option>)}</select></div>
            <div className="filter-group"><label className="filter-label" htmlFor="category">Sector</label><select className="select" id="category" value={category} onChange={(event) => setCategory(event.target.value)}><option value="">All sectors</option>{categories.map((item) => <option value={item} key={item}>{item}</option>)}</select></div>
          </aside>
          <div>
            <div className="catalogue-top"><label className="sr-only" htmlFor="scheme-search">Search schemes</label><input className="field" id="scheme-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by scheme name, benefit or sector…" /><span className="result-count">{filtered.length} {filtered.length === 1 ? "record" : "records"}</span></div>
            {loading ? <div className="loading">Loading the catalogue…</div> : loadError ? <div className="empty-state" role="alert">Catalogue unavailable. <button onClick={() => window.location.reload()}>Retry</button></div> : visible.length ? <div className="scheme-grid">{visible.map((scheme) => <SchemeCard scheme={scheme} key={scheme.scheme_id} />)}</div> : <div className="empty-state">No schemes match those filters. Try clearing one filter or searching a broader phrase.</div>}
            {limit && filtered.length > limit && <div style={{ marginTop: 17 }}><Link className="btn btn-ghost" href="/schemes">View all {filtered.length} matches <span aria-hidden="true">→</span></Link></div>}
          </div>
        </div>
      </div>
    </section>
  );
}

function unique(values: string[]) { return Array.from(new Set(values)).sort((a, b) => a.localeCompare(b)); }
function shortJurisdiction(value: string) { return value.length > 38 ? `${value.slice(0, 36)}…` : value; }
