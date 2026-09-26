import React from "react";
export function BpmnData({ kind = "object", label }) {
  const store = kind === "store";
  return (
    <div className="gw-bpmn-data">
      <svg width="44" height="52" viewBox="0 0 44 52" aria-hidden="true">
        {store ? (
          <g fill="var(--paper)" stroke="currentColor" strokeWidth="2"><path d="M3 10v32c0 5 38 5 38 0V10" /><ellipse cx="22" cy="10" rx="19" ry="6" /><path d="M3 17c0 5 38 5 38 0" fill="none" /></g>
        ) : (
          <path d="M3 2h26l12 12v36H3z M29 2v12h12" fill="var(--paper)" stroke="currentColor" strokeWidth="2" />
        )}
      </svg>
      <div className="gw-under">{label || <em className="quiet">{store ? "Where is it kept?" : "Which document?"}</em>}</div>
    </div>
  );
}
