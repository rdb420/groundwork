import React from "react";
export function CheckItem({ level = "ask", children, onShow }) {
  return <li className={"gw-chk chk-" + level}><span>{children}</span>{onShow && <button type="button" className="gw-btn gw-btn--link" onClick={onShow}>Show</button>}</li>;
}
