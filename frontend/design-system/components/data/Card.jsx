import React from "react";
export function Card({ variant = "card", header, children, className, ...rest }) {
  const base = { card: "gw-card", center: "gw-center-card", form: "gw-newboard" }[variant] || "gw-card";
  return <div className={base + (className ? " " + className : "")} {...rest}>{header && <header>{header}</header>}{children}</div>;
}
