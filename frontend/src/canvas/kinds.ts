// Mirror of backend/app/live/vocabulary.py. Keep the two in step.
export type Kind =
  | "start" | "task" | "manual_task" | "system_task" | "rule_task" | "subprocess" | "decision" | "parallel" | "wait" | "end"
  | "external_party" | "stakeholder" | "application" | "document" | "workaround" | "issue" | "risk" | "control"
  | "metric" | "question" | "unclear" | "note";

export const FLOW_KINDS = new Set<Kind>(["start", "task", "manual_task", "system_task", "rule_task", "subprocess", "decision", "parallel", "wait", "end", "unclear"]);

type Spec = { type: string; data?: Record<string, unknown>; size?: { width: number; height: number }; zIndex?: number };
export const NODE_FOR_KIND: Record<Kind, Spec> = {
  start: { type: "bpmnStart" },
  end: { type: "bpmnEnd" },
  wait: { type: "bpmnIntermediate" },
  task: { type: "bpmnTask", size: { width: 150, height: 64 } },
  manual_task: { type: "bpmnTask", data: { taskKind: "manual" }, size: { width: 150, height: 64 } },
  system_task: { type: "bpmnTask", data: { taskKind: "system" }, size: { width: 150, height: 64 } },
  rule_task: { type: "bpmnTask", data: { taskKind: "rule" }, size: { width: 160, height: 64 } },
  subprocess: { type: "bpmnSubprocess", size: { width: 160, height: 70 } },
  decision: { type: "bpmnGateway", data: { gatewayType: "exclusive" } },
  parallel: { type: "bpmnGateway", data: { gatewayType: "parallel" } },
  unclear: { type: "adhoc", size: { width: 220, height: 110 } },
  document: { type: "bpmnData", data: { dataKind: "object" } },
  external_party: { type: "pool", size: { width: 900, height: 56 }, zIndex: -1 },
  stakeholder: { type: "stakeholder", size: { width: 150, height: 48 } },
  application: { type: "application", size: { width: 150, height: 48 } },
  workaround: { type: "workaround", size: { width: 170, height: 60 } },
  issue: { type: "issue", size: { width: 170, height: 60 } },
  risk: { type: "risk", size: { width: 170, height: 60 } },
  control: { type: "control", size: { width: 160, height: 48 } },
  metric: { type: "metric", size: { width: 140, height: 48 } },
  question: { type: "question", size: { width: 170, height: 60 } },
  note: { type: "sticky", size: { width: 160, height: 110 } },
};

export const KIND_LABEL: Record<Kind, string> = {
  start: "Start", task: "Step", manual_task: "Manual step", system_task: "System step", rule_task: "Rule step",
  subprocess: "Sub-process", decision: "Decision", parallel: "In parallel", wait: "Wait", end: "End",
  external_party: "Outside party", stakeholder: "Person", application: "Application", document: "Document",
  workaround: "Workaround", issue: "Issue", risk: "Risk", control: "Check or approval", metric: "Number",
  question: "Open question", unclear: "Unclear area", note: "Note",
};

export function kindOf(node: { type?: string; data?: any }): Kind {
  const d = node.data || {};
  switch (node.type) {
    case "bpmnTask": return ({ manual: "manual_task", system: "system_task", rule: "rule_task" } as Record<string, Kind>)[d.taskKind] ?? "task";
    case "bpmnSubprocess": return "subprocess";
    case "bpmnGateway": return d.gatewayType === "parallel" ? "parallel" : "decision";
    case "bpmnData": return "document";
    case "bpmnStart": return "start";
    case "bpmnEnd": return "end";
    case "bpmnIntermediate": return "wait";
    case "pool": return "external_party";
    case "adhoc": return "unclear";
    case "sticky": case "text": return "note";
    default: return (node.type as Kind) in NODE_FOR_KIND ? (node.type as Kind) : "note";
  }
}

// Layers the facilitator can show or hide. The standard path is always visible.
export const LAYERS = {
  parties: { label: "People and outside parties", types: ["stakeholder", "pool"] },
  systems: { label: "Systems and documents", types: ["application", "bpmnData"] },
  problems: { label: "Issues, risks and workarounds", types: ["issue", "risk", "workaround"] },
  controls: { label: "Checks and numbers", types: ["control", "metric"] },
  notes: { label: "Questions and notes", types: ["question", "sticky", "text", "image"] },
  suggestions: { label: "Suggestions waiting for a decision", types: [] as string[] },
} as const;
export type Layer = keyof typeof LAYERS;
