import React from "react";
export function Passbar({ pass = "overview", children }) {
  return <div className={"gw-passbar" + (pass === "detail" ? " pass-detail" : "")}>{children}</div>;
}
