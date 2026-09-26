import React from "react";
const cx = (...a) => a.filter(Boolean).join(" ");

export function Tag({ kind = "pi", children, className }) {
  if (kind === "pi") return <span className={cx("gw-pi", className)}>{children || "Personal info"}</span>;
  if (kind === "overview" || kind === "detail") return <span className={cx("gw-passtag", kind === "overview" && "pass-overview", className)}>{children}</span>;
  return <span className={cx("gw-tag", kind === "workaround" && "t-workaround", kind === "issue" && "t-issue", className)}>{children}</span>;
}
