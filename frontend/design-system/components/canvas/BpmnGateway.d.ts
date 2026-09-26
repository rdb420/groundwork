import * as React from "react";
/** BPMN gateway diamond. exclusive ×, parallel +, inclusive ○. Label is a question ("Paid in full?"). */
export interface BpmnGatewayProps { type?: "exclusive" | "parallel" | "inclusive"; label?: string; suggested?: boolean; pending?: boolean; selected?: boolean; }
export function BpmnGateway(props: BpmnGatewayProps): JSX.Element;
