import React from "react";
const cx = (...a) => a.filter(Boolean).join(" ");

export function Button({ variant = "default", size, on, href, className, children, ...rest }) {
  const cls = cx("gw-btn", variant === "primary" && "gw-btn--primary", variant === "link" && "gw-btn--link", size === "small" && "gw-btn--small", on && "gw-btn--on", className);
  if (href) return <a className={cls} href={href} {...rest}>{children}</a>;
  return <button type="button" className={cls} {...rest}>{children}</button>;
}
