import React from "react";
export function GroundworkMark({ size = 26 }) {
  return (
    <svg width={size} height={size * 18 / 26} viewBox="0 0 34 22" aria-hidden="true">
      <circle cx="7" cy="11" r="5.5" fill="none" stroke="currentColor" strokeWidth="2.5" />
      <path d="M12.5 11H19" stroke="currentColor" strokeWidth="2.5" />
      <rect x="19" y="3" width="14" height="16" rx="3" fill="currentColor" />
    </svg>
  );
}
export function BrandMark({ name = "Groundwork", big, mark = true }) {
  return <span className="gw-brand" style={big ? { fontSize: "1.25rem" } : undefined}>{mark && <GroundworkMark />}{name}</span>;
}
export function YshLockup({ src = "assets/logo/ysh-logo-white.png", height = 40, onDark = true }) {
  return <img src={src} alt="YSH Property" style={{ height, display: "block", filter: onDark ? undefined : "invert(1) brightness(.2)" }} />;
}
