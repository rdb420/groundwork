import React from "react";
const cx = (...a) => a.filter(Boolean).join(" ");

export function BpmnEvent({ kind = "start", label, suggested, pending, selected }) {
  const ph = kind === "start" ? "What starts it?" : kind === "end" ? "Outcome" : "Event";
  return (
    <div className={cx("gw-bpmn-event", kind, suggested && "gw-suggested", pending && "gw-pending")}>
      <div className={cx("ring", selected && "gw-sel")} />
      <div className="gw-under">{label || <em className="quiet">{ph}</em>}</div>
    </div>
  );
}
