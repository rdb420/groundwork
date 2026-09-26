import React from "react";
export function Dialog({ open = true, title, children, actions, onClose, inline }) {
  if (!open) return null;
  const box = <div className="gw-dialog" role="dialog" aria-modal="true" aria-label={typeof title === "string" ? title : undefined}>{title && <h2>{title}</h2>}{children}{actions && <div className="gw-actions">{actions}</div>}</div>;
  if (inline) return box;
  return <div className="gw-scrim" onClick={(e) => e.target === e.currentTarget && onClose && onClose()}>{box}</div>;
}
