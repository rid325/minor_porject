import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nagrik Path — Citizen Scheme Information Portal",
  description: "A structured information and pre-screening portal for government schemes.",
};

function Mark() {
  return <span className="brand-mark" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 16.5V4.25M10 4.25 5.8 8.45M10 4.25l4.2 4.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/><path d="M3.5 16.5h13" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg></span>;
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="site-shell">
          <header className="site-header">
            <Link className="brand" href="/">
              <Mark />
              <span>Nagrik Path<small>citizen scheme information portal</small></span>
            </Link>
            <nav className="nav desktop-nav" aria-label="Primary navigation">
              <Link className="nav-link" href="/schemes">Scheme catalogue</Link>
              <Link className="nav-link" href="/profile">Eligibility profile</Link>
              <Link className="nav-link nav-cta" href="/results">View assessment <span aria-hidden="true">↗</span></Link>
            </nav>
            <Link className="mobile-nav" href="/profile" aria-label="Open profile">Profile <span aria-hidden="true">→</span></Link>
          </header>
          {children}
          <footer className="footer">
            <div className="page-wrap footer-inner">
              <p>© 2026 Nagrik Path · Citizen Scheme Information Portal</p>
              <p>Information support only. Final eligibility is decided by the implementing department.</p>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
