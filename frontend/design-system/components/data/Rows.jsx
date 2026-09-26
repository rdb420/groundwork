import React from "react";
export function Rows({ items = [] }) {
  return <ul className="gw-rows">{items.map((r, i) => <li key={i}>{r.map((c, j) => <span key={j} className={j === 1 ? "quiet" : undefined}>{c}</span>)}</li>)}</ul>;
}
