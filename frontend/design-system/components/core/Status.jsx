import React from "react";
const cx = (...a) => a.filter(Boolean).join(" ");

const TONE = { processed: "s-processed", ok: "s-processed", done: "s-processed", failed: "s-failed", error: "s-failed" };
export function Status({ tone = "info", children, className }) {
  return <span className={cx("gw-status", TONE[tone], className)}>{children}</span>;
}
