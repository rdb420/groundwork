import * as React from "react";
/** BPMN event circle. Start = green 2px ring, intermediate = double ring, end = 5px ink ring. Label sits underneath. Object + past tense ("Rent received"). */
export interface BpmnEventProps { kind?: "start" | "intermediate" | "end"; label?: string; suggested?: boolean; pending?: boolean; selected?: boolean; }
export function BpmnEvent(props: BpmnEventProps): JSX.Element;
