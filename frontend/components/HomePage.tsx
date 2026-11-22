import Link from "next/link";
import Catalogue from "./Catalogue";

export default function HomePage() {
  return (
    <main>
      <section className="page-wrap hero">
        <div>
          <span className="eyebrow">Citizen services · information and guidance</span>
          <h1>Understand schemes. <span>Plan your next step.</span></h1>
          <p className="hero-copy">Yojna Connect organises government scheme information by jurisdiction, benefit and application route. Complete an optional profile to receive an explainable, preliminary eligibility assessment.</p>
          <div className="hero-actions"><Link className="btn btn-primary" href="/schemes">Open scheme catalogue <span aria-hidden="true">↗</span></Link><Link className="btn btn-secondary" href="/profile">Complete eligibility profile <span aria-hidden="true">→</span></Link></div>
          <div className="hero-note"><svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><circle cx="8" cy="8" r="6.3" stroke="currentColor" strokeWidth="1.4"/><path d="M8 7.1v4M8 4.5h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg><span>Pre-screening only. The relevant department, bank or service centre makes the final decision after verifying the applicant's documents.</span></div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="hero-orbit" />
          <div className="float-tag one"><span className="float-dot" /> 75 schemes, one place</div>
          <div className="float-tag two"><span className="float-dot" style={{ background: "var(--brand)" }} /> Your answers stay local</div>
          <div className="hero-card">
            <div className="hero-card-label"><span>Illustrative assessment</span><span>01 / 03</span></div>
            <h3>Pradhan Mantri Kisan Samman Nidhi</h3>
            <p>Income support for eligible farmer families recorded in State or UT land records.</p>
            <div className="mini-eligibility"><span>Preliminary result</span><strong>₹6k</strong></div>
          </div>
        </div>
      </section>
      <section className="page-wrap section" style={{ paddingTop: 12, paddingBottom: 25 }}>
        <div className="section-head"><div><span className="eyebrow">Using the portal</span><h2>A clear three-step process.</h2></div></div>
        <div className="stat-strip" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
          <div className="stat-card"><strong>01</strong><span><b>Review the catalogue.</b><br />Compare benefits, jurisdictions, documents and application routes.</span></div>
          <div className="stat-card"><strong>02</strong><span><b>Complete your profile.</b><br />Provide only the information needed for preliminary screening.</span></div>
          <div className="stat-card"><strong>03</strong><span><b>Review the assessment.</b><br />See passed, failed and unresolved conditions with reasons.</span></div>
        </div>
      </section>
      <Catalogue limit={6} embedded />
      <Link className="chat-assistant" href="/chat" aria-label="Open the Yojna Connect assistant" title="Ask Yojna Connect">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M19.5 11.4a7.5 7.5 0 0 1-8.8 7.4 8.5 8.5 0 0 1-3.3-.2L4 20l1.1-3.1A7.5 7.5 0 1 1 19.5 11.4Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
          <path d="M8.5 11.5h.01M12 11.5h.01M15.5 11.5h.01" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
        </svg>
        <span>Ask Yojna</span>
      </Link>
    </main>
  );
}
