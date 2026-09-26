import * as React from "react";
/** BPMN data object (folded page) or data store (cylinder). */
export interface BpmnDataProps { kind?: "object" | "store"; label?: string; }
export function BpmnData(props: BpmnDataProps): JSX.Element;
