// App identity and navigation from the design system (design-system/components/navigation).
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import yshLogoWhite from "../../design-system/assets/logo/ysh-logo-white.png";
import { cx } from "./core";

// Start event, sequence flow, task: the Groundwork mark, drawn in currentColor.
export function GroundworkMark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={(size * 18) / 26} viewBox="0 0 34 22" aria-hidden="true">
      <circle cx="7" cy="11" r="5.5" fill="none" stroke="currentColor" strokeWidth="2.5" />
      <path d="M12.5 11H19" stroke="currentColor" strokeWidth="2.5" />
      <rect x="19" y="3" width="14" height="16" rx="3" fill="currentColor" />
    </svg>
  );
}

export function BrandMark({ name = "Groundwork", big, mark = true }: { name?: ReactNode; big?: boolean; mark?: boolean }) {
  return <span className={cx("gw-brand", big && "big")}>{mark && <GroundworkMark />} {name}</span>;
}

// The YSH Property logo. The file is white, for dark or survey-blue backgrounds.
export function YshLockup({ src = yshLogoWhite, height = 40, onDark = true }: { src?: string; height?: number; onDark?: boolean }) {
  return <img className={cx("gw-lockup", !onDark && "on-light")} src={src} alt="YSH Property" height={height} />;
}

// The sticky top bar: brand, text navigation with the active page underlined, then who is signed in.
export function Topbar({ appName, links, who, onSignOut }: {
  appName?: ReactNode; links: [to: string, label: ReactNode][]; who?: ReactNode; onSignOut?: () => void;
}) {
  return (
    <header className="gw-topbar">
      <NavLink to="/" className="gw-brand" aria-label="Home"><GroundworkMark /> {appName}</NavLink>
      <nav aria-label="Main">
        {links.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}
      </nav>
      <div className="gw-who">
        {who && <span>{who}</span>}
        {onSignOut && <button type="button" className="gw-btn gw-btn--link" onClick={onSignOut}>Sign out</button>}
      </div>
    </header>
  );
}
