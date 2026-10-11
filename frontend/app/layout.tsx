import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nagrik Path — Government scheme finder",
  description: "Browse government schemes and understand which conditions to check before applying.",
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
              <span>Nagrik Path<small>scheme finder</small></span>
            </Link>
            <nav className="nav desktop-nav" aria-label="Primary navigation">
              <Link className="nav-link" href="/schemes">Browse schemes</Link>
              <Link className="nav-link" href="/profile">My profile</Link>
              <Link className="nav-link nav-cta" href="/results">See my matches <span aria-hidden="true">↗</span></Link>
            </nav>
            <Link className="mobile-nav" href="/profile" aria-label="Open profile">Profile <span aria-hidden="true">→</span></Link>
          </header>
          {children}
          <footer className="footer">
            <div className="page-wrap footer-inner">
              <p>© 2026 Nagrik Path · A pre-screening guide, not an approval decision.</p>
              <p>Profile answers stay in this browser until you choose to run a check.</p>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
