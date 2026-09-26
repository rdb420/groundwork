import * as React from "react";
/** Context around steps. Each kind has one visual cue: person = pill, system = thick survey left edge, workaround = dashed marker-yellow, issue = red tint, risk = thick red left edge, check = thick green left edge, number = dotted, to confirm = hatched dashed. */
export interface ContextNodeProps {
  kind?: "stakeholder" | "application" | "workaround" | "issue" | "control" | "metric" | "question" | "risk";
  label?: string;
  width?: number;
  height?: number;
  suggested?: boolean;
  pending?: boolean;
}
export function ContextNode(props: ContextNodeProps): JSX.Element;
