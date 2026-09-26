import React from "react";
export function Tiles({ items = [] }) {
  return <dl className="gw-tiles">{items.map((t, i) => <div key={i}><dt>{t.label}</dt><dd>{t.value}</dd>{t.note && <span className="quiet">{t.note}</span>}</div>)}</dl>;
}
