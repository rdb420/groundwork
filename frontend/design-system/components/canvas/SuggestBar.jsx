import React from "react";
export function SuggestBar({ who = "Suggested", change, onKeep, onDrop, style }) {
  return (
    <div className={"gw-suggest-bar" + (change ? " change" : "")} style={style}>
      <span>{who}{change ? ": " + change : ""}</span>
      <button type="button" className="gw-btn" onClick={onKeep}>{change ? "Accept" : "Keep"}</button>
      <button type="button" className="gw-btn" onClick={onDrop}>{change ? "Reject" : "Drop"}</button>
    </div>
  );
}
