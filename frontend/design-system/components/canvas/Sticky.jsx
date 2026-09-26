import React from "react";
export function Sticky({ children, width = 160, height = 120, rotate = 0, suggested }) {
  return <div style={{ width, height, transform: rotate ? "rotate(" + rotate + "deg)" : undefined }}><div className={"gw-sticky" + (suggested ? " gw-suggested" : "")} style={suggested ? { border: "2px dashed var(--survey)" } : undefined}>{children}</div></div>;
}
