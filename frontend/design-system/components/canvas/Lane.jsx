import React from "react";
export function Lane({ label, width = 900, height = 200, children }) {
  return <div style={{ width, height, position: "relative" }}><div className="gw-lane"><div className="gw-lane-head">{label}</div><div style={{ position: "relative", flex: 1 }}>{children}</div></div></div>;
}
export function Pool({ label, width = 900, height = 56 }) {
  return <div style={{ width, height }}><div className="gw-pool"><span className="gw-pool-mark">Outside party</span>{label}</div></div>;
}
export function UnclearArea({ label, width = 220, height = 110 }) {
  return <div style={{ width, height }}><div className="gw-adhoc"><span className="gw-ctx-mark">Unclear</span><div>{label}</div><span className="tilde" aria-hidden="true">~</span></div></div>;
}
