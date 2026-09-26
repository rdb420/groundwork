import React from "react";
import { BrandMark } from "./BrandMark.jsx";
export function Topbar({ appName = "Groundwork", links = [], active, onNavigate, who, onSignOut }) {
  return (
    <header className="gw-topbar">
      <a className="gw-brand" href="#" onClick={(e) => { e.preventDefault(); onNavigate && onNavigate("home"); }} aria-label="Home"><BrandMark name={appName} /></a>
      <nav aria-label="Main">
        {links.map(([k, l]) => <a key={k} className={active === k ? "active" : undefined} onClick={(e) => { e.preventDefault(); onNavigate && onNavigate(k); }} href="#">{l}</a>)}
      </nav>
      <div className="gw-who">{who && <span>{who}</span>}{onSignOut && <button type="button" className="gw-btn gw-btn--link" onClick={onSignOut}>Sign out</button>}</div>
    </header>
  );
}
