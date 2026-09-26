import React from "react";
export function Popover({ open, children, style }) {
  if (!open) return null;
  return <div className="gw-popover" role="group" style={style}>{children}</div>;
}
