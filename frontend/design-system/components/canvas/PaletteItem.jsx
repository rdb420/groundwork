import React from "react";
export function PaletteItem({ itemKey, children, onClick }) {
  return <button type="button" draggable className={"gw-pitem pi-" + itemKey} onClick={onClick}><span className="gw-glyph" aria-hidden="true" />{children}</button>;
}
export function PaletteGroup({ title, children }) { return <div className="gw-pgroup"><h4>{title}</h4>{children}</div>; }
export function FlowPick({ flow = "sequence", on, children, onChange }) {
  return <label className={"gw-flowpick" + (on ? " on" : "")}><input type="radio" name="flow" checked={!!on} onChange={onChange} /><span className={"gw-flowline fl-" + flow} aria-hidden="true" />{children}</label>;
}
