import React from "react";
export function Chip({ children, onRemove }) {
  return <span className="gw-chip">{children}{onRemove && <button type="button" aria-label="Remove" onClick={onRemove}>×</button>}</span>;
}
