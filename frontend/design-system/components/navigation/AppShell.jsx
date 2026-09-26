import React from "react";
import { BrandMark } from "./BrandMark.jsx";
export function AppShell({ appName = "Internal Business Application", status, nav = [], active, onNavigate, children, mobileNav }) {
  const go = (k) => (e) => { e.preventDefault(); onNavigate && onNavigate(k); };
  return (
    <div className="ibs-shell">
      <header className="ibs-header">
        <div className="ibs-brand"><span className="gw-brand" style={{ color: "var(--survey)" }}><BrandMark name={appName} /></span></div>
        <div className="ibs-utility">{status && <span className="ibs-pill">{status}</span>}</div>
      </header>
      <aside className="ibs-nav" aria-label="Primary navigation">
        {nav.map((g, i) => (
          <div key={i}>{g.title && <h4>{g.title}</h4>}{g.items.map(([k, l]) => <a key={k} href="#" className={active === k ? "active" : undefined} onClick={go(k)}>{l}</a>)}</div>
        ))}
      </aside>
      <main className="ibs-content" id="main-content" tabIndex={-1}>{children}</main>
      <nav className="ibs-mobile-nav" aria-label="Primary navigation">
        {(mobileNav || nav.flatMap((g) => g.items).slice(0, 3)).map(([k, l]) => <a key={k} href="#" className={active === k ? "active" : undefined} onClick={go(k)}>{l}</a>)}
      </nav>
    </div>
  );
}
