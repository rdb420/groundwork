import React from "react";
export function CombineBar({ children, actions, floating = true }) {
  const style = floating ? { position: "fixed", left: "50%", bottom: "1.2rem", transform: "translateX(-50%)", zIndex: 6, width: "min(760px, calc(100% - 2rem))" } : undefined;
  return <div className="gw-combine-bar" role="region" style={style}><p>{children}</p>{actions}</div>;
}
