import * as React from "react";
/** BPMN task: white box, 2px ink border, 10px radius. taskKind adds the corner marker (user/system/rule/manual; manual is dashed). Verb + object ("Check bank feed"). */
export interface BpmnTaskProps {
  label?: string;
  taskKind?: "user" | "system" | "rule" | "manual";
  sub?: boolean;
  tags?: Array<"workaround" | "issue" | string>;
  suggested?: boolean;
  pending?: boolean;
  selected?: boolean;
  width?: number;
  height?: number;
  /** Optional SuggestBar rendered above the node. */
  suggestBar?: React.ReactNode;
}
export function BpmnTask(props: BpmnTaskProps): JSX.Element;
