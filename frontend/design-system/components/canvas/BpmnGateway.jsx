import React from "react";
const cx = (...a) => a.filter(Boolean).join(" ");

export function BpmnGateway({ type = "exclusive", label, suggested, pending, selected }) {
  const mark = type === "parallel" ? "+" : type === "inclusive" ? "○" : "×";
  return (
    <div className={cx("gw-bpmn-gateway", suggested && "gw-suggested", pending && "gw-pending")}>
      <div className={cx("diamond", selected && "gw-sel")}><span>{mark}</span></div>
      <div className="gw-under">{label || <em className="quiet">Decision?</em>}</div>
    </div>
  );
}
