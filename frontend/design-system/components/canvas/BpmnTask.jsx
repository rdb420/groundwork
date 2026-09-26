import React from "react";
const cx = (...a) => a.filter(Boolean).join(" ");

const ICON = {
  user: <svg viewBox="0 0 16 16" width="15" height="15"><circle cx="8" cy="5" r="3" fill="none" stroke="currentColor" strokeWidth="1.4" /><path d="M2.5 15c0-3.5 2.5-5.5 5.5-5.5s5.5 2 5.5 5.5" fill="none" stroke="currentColor" strokeWidth="1.4" /></svg>,
  rule: <svg viewBox="0 0 16 16" width="15" height="15"><rect x="1.5" y="2.5" width="13" height="11" fill="none" stroke="currentColor" strokeWidth="1.3" /><path d="M1.5 6h13M1.5 9.5h13M6 2.5v11" stroke="currentColor" strokeWidth="1.1" /></svg>,
  manual: <svg viewBox="0 0 16 16" width="15" height="15"><path d="M4 14V7.5a1.2 1.2 0 0 1 2.4 0V9M6.4 9V3.5a1.2 1.2 0 0 1 2.4 0V8.5M8.8 8.5V4.5a1.2 1.2 0 0 1 2.4 0V9M11.2 9V6.5a1.2 1.2 0 0 1 2.4 0V11c0 2-1.5 3-3.5 3H7" fill="none" stroke="currentColor" strokeWidth="1.3" /></svg>,
  system: <svg viewBox="0 0 16 16" width="15" height="15"><circle cx="8" cy="8" r="2.4" fill="none" stroke="currentColor" strokeWidth="1.4" /><path d="M8 1.5v2.2M8 12.3v2.2M1.5 8h2.2M12.3 8h2.2M3.4 3.4l1.6 1.6M11 11l1.6 1.6M3.4 12.6L5 11M11 5l1.6-1.6" stroke="currentColor" strokeWidth="1.4" /></svg>,
};
export function BpmnTask({ label, taskKind, sub, tags = [], suggested, pending, selected, width = 150, height = 64, suggestBar }) {
  return (
    <div style={{ width, height, position: "relative" }}>
      {suggestBar}
      <div className={cx("gw-bpmn-task", taskKind === "manual" && "manual", ICON[taskKind] && "has-icon", suggested && "gw-suggested", pending && "gw-pending", selected && "gw-sel")}>
        {ICON[taskKind] && <span className="gw-task-icon" aria-hidden="true">{ICON[taskKind]}</span>}
        <span>{label || <em className="quiet">What happens?</em>}</span>
        {sub && <span className="plus" aria-hidden="true">+</span>}
        {tags.length > 0 && <div className="gw-tags">{tags.map((t) => <span key={t} className={"gw-tag t-" + t}>{t}</span>)}</div>}
      </div>
    </div>
  );
}
