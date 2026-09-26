import React from "react";
export function ReviewCard({ time, model, summary, children, actions }) {
  return (
    <article className="gw-review">
      <header><strong>Review at {time}</strong><span className="quiet">{model}</span></header>
      {summary && <p>{summary}</p>}
      {actions}
      {children && <ul className="gw-oplist">{children}</ul>}
    </article>
  );
}
export function ReviewOp({ done, children, reason, actions }) {
  return <li className={done ? "done" : undefined}><span>{children}</span>{reason && <span className="quiet">{reason}</span>}{!done && actions && <span className="gw-opbtns">{actions}</span>}</li>;
}
