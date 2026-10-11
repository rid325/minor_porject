import Link from "next/link";
import Catalogue from "./Catalogue";

export default function HomePage() {
  return (
    <main>
      <section className="page-wrap hero">
        <div>
          <span className="eyebrow">A calmer way to get oriented</span>
          <h1>Find the support that fits <span>your life.</span></h1>
          <p className="hero-copy">There are hundreds of government schemes. Nagrik Path brings the useful details into one clear place, then helps you see which questions matter for your situation.</p>
          <div className="hero-actions"><Link className="btn btn-primary" href="/schemes">Explore the catalogue <span aria-hidden="true">↗</span></Link><Link className="btn btn-secondary" href="/profile">Build my profile <span aria-hidden="true">→</span></Link></div>
          <div className="hero-note"><svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><circle cx="8" cy="8" r="6.3" stroke="currentColor" strokeWidth="1.4"/><path d="M8 7.1v4M8 4.5h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg><span>This is a pre-screening guide, not an approval decision. The department or bank makes the final call after checking your documents.</span></div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="hero-orbit" />
          <div className="float-tag one"><span className="float-dot" /> 75 schemes, one place</div>
          <div className="float-tag two"><span className="float-dot" style={{ background: "var(--brand)" }} /> Your answers stay local</div>
          <div className="hero-card">
            <div className="hero-card-label"><span>A small example</span><span>01 / 03</span></div>
            <h3>Pradhan Mantri Kisan Samman Nidhi</h3>
            <p>Income support for eligible farmer families recorded in State or UT land records.</p>
            <div className="mini-eligibility"><span>Likely eligible to explore</span><strong>₹6k</strong></div>
          </div>
        </div>
      </section>
      <section className="page-wrap section" style={{ paddingTop: 12, paddingBottom: 25 }}>
        <div className="section-head"><div><span className="eyebrow">How it works</span><h2>Three useful steps.</h2></div></div>
        <div className="stat-strip" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
          <div className="stat-card"><strong>01</strong><span><b>Browse without signing up.</b><br />Understand benefits, routes, and cautions before sharing anything.</span></div>
          <div className="stat-card"><strong>02</strong><span><b>Tell us what matters.</b><br />Answer a short, structured profile at your own pace.</span></div>
          <div className="stat-card"><strong>03</strong><span><b>Get an explained shortlist.</b><br />See what looks promising, what needs checking, and why.</span></div>
        </div>
      </section>
      <Catalogue limit={6} embedded />
    </main>
  );
}
