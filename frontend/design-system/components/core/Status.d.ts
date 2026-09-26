import * as React from "react";
/** Rounded status pill. Info (survey), ok (green) or error (boundary red). */
export interface StatusProps {
  tone?: "info" | "ok" | "processed" | "done" | "error" | "failed";
  children?: React.ReactNode;
  className?: string;
}
export function Status(props: StatusProps): JSX.Element;
