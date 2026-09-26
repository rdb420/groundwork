import React from "react";
export function Drawer({ open = true, title, children, onClose, inline }) {
  if (!open) return null;
  const style = inline ? { position: "relative", width: "100%", height: "100%" } : undefined;
  return (
    <aside className="gw-drawer" style={style} aria-label={typeof title === "string" ? title : "Detail"}>
      {onClose && <button type="button" className="gw-btn gw-btn--link close" onClick={onClose}>Close</button>}
      {title && <h2 style={{ marginTop: 0 }}>{title}</h2>}
      {children}
    </aside>
  );
}
export function DetailList({ items = [] }) {
  return <dl>{items.map(([k, v], i) => <React.Fragment key={i}><dt>{k}</dt><dd>{v}</dd></React.Fragment>)}</dl>;
}
