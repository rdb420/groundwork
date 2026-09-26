import React from "react";
const META = { stakeholder: "Person", application: "System", workaround: "Workaround", issue: "Issue", control: "Check", metric: "Number", question: "To confirm", risk: "Risk" };
export function ContextNode({ kind = "stakeholder", label, width = 170, height = 60, suggested, pending }) {
  return (
    <div style={{ width, minHeight: height }}>
      <div className={"gw-ctx " + kind + (suggested ? " gw-suggested" : "") + (pending ? " gw-pending" : "")}>
        <span className="gw-ctx-mark">{META[kind]}</span><span>{label}</span>
      </div>
    </div>
  );
}
