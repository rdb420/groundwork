// Canvas palette and proposal pieces from the design system (design-system/components/canvas).
// The BPMN shapes themselves are React Flow nodes in canvas/nodes.tsx, drawn with the same classes.
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cx } from "./core";

// A palette entry: a CSS glyph of the element's shape and a plain-language name.
export function PaletteItem({ itemKey, children, className, ...rest }: { itemKey: string; children?: ReactNode } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" className={cx("gw-pitem", `pi-${itemKey}`, className)} {...rest}>
      <span className="gw-glyph" aria-hidden="true" />{children}
    </button>
  );
}

export function PaletteGroup({ title, children }: { title: ReactNode; children?: ReactNode }) {
  return <div className="gw-pgroup"><h4>{title}</h4>{children}</div>;
}

// Which kind of connector new links use.
export function FlowPick({ flow, on, onChange, children }: { flow: string; on?: boolean; onChange: () => void; children?: ReactNode }) {
  return (
    <label className={cx("gw-flowpick", on && "on")}>
      <input type="radio" name="flow" checked={!!on} onChange={onChange} />
      <span className={cx("gw-flowline", `fl-${flow}`)} aria-hidden="true" />{children}
    </label>
  );
}

// The bar above a proposed element: Keep or Drop a new one, Accept or Reject a change to one.
export function SuggestBar({ who = "Suggested", change, title, onKeep, onDrop, className }: {
  who?: ReactNode; change?: ReactNode; title?: string; onKeep: () => void; onDrop: () => void; className?: string;
}) {
  return (
    <div className={cx("gw-suggest-bar", change != null && "change", className)} title={title}>
      <span>{who}{change != null ? <>: {change}</> : null}</span>
      <button type="button" className="gw-btn" onClick={onKeep}>{change != null ? "Accept" : "Keep"}</button>
      <button type="button" className="gw-btn" onClick={onDrop}>{change != null ? "Reject" : "Drop"}</button>
    </div>
  );
}
