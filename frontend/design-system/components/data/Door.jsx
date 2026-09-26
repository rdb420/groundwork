import React from "react";
export function Door({ title, children, href = "#", onClick }) {
  return <a className="gw-door" href={href} onClick={onClick}><strong>{title}</strong><span>{children}</span></a>;
}
export function Doors({ children }) { return <div className="gw-doors">{children}</div>; }
