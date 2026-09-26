import React from "react";
export function OpLine({ auto, children, confidence, actions }) {
  return (
    <div className={"gw-opline" + (auto ? " auto" : "")}>
      <span>{children}</span>
      <span className="gw-conf">{auto ? "added" : "waiting"}{confidence != null ? " · " + Math.round(confidence * 100) + "%" : ""}</span>
      {actions && <span className="gw-opbtns">{actions}</span>}
    </div>
  );
}
export function Heard({ said, children }) { return <li style={{ padding: "0.5rem 0", borderBottom: "1px solid var(--line)", listStyle: "none" }}><p className="gw-said">{said}</p>{children}</li>; }
