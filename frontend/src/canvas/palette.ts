// What the palette offers. Each item seeds a node's type, size and data.
export type PaletteItem = { key: string; label: string; type: string; data?: Record<string, unknown>; size?: { width: number; height: number }; zIndex?: number; group: string };

export const PALETTE: PaletteItem[] = [
  { key: "start", label: "Start", type: "bpmnStart", group: "Flow" },
  { key: "task", label: "Task", type: "bpmnTask", size: { width: 150, height: 64 }, group: "Flow" },
  { key: "user", label: "Person does it", type: "bpmnTask", data: { taskKind: "user" }, size: { width: 150, height: 64 }, group: "Flow" },
  { key: "manual", label: "Done by hand", type: "bpmnTask", data: { taskKind: "manual" }, size: { width: 150, height: 64 }, group: "Flow" },
  { key: "system", label: "System does it", type: "bpmnTask", data: { taskKind: "system" }, size: { width: 150, height: 64 }, group: "Flow" },
  { key: "rule", label: "Rule step", type: "bpmnTask", data: { taskKind: "rule" }, size: { width: 160, height: 64 }, group: "Flow" },
  { key: "sub", label: "Sub-process", type: "bpmnSubprocess", size: { width: 160, height: 70 }, group: "Flow" },
  { key: "xor", label: "Decision", type: "bpmnGateway", data: { gatewayType: "exclusive" }, group: "Flow" },
  { key: "and", label: "In parallel", type: "bpmnGateway", data: { gatewayType: "parallel" }, group: "Flow" },
  { key: "wait", label: "Wait or event", type: "bpmnIntermediate", group: "Flow" },
  { key: "end", label: "End", type: "bpmnEnd", group: "Flow" },
  { key: "unclear", label: "Unclear area", type: "adhoc", size: { width: 220, height: 110 }, group: "Flow" },
  { key: "doc", label: "Document", type: "bpmnData", data: { dataKind: "object" }, group: "Things" },
  { key: "store", label: "System or store", type: "bpmnData", data: { dataKind: "store" }, group: "Things" },
  { key: "lane", label: "Lane (who)", type: "lane", size: { width: 900, height: 200 }, zIndex: -1, group: "Things" },
  { key: "pool", label: "Outside party", type: "pool", size: { width: 900, height: 56 }, zIndex: -1, group: "Context" },
  { key: "stakeholder", label: "Person", type: "stakeholder", size: { width: 150, height: 48 }, group: "Context" },
  { key: "application", label: "Application", type: "application", size: { width: 150, height: 48 }, group: "Context" },
  { key: "workaround", label: "Workaround", type: "workaround", size: { width: 170, height: 60 }, group: "Context" },
  { key: "issue", label: "Issue or error", type: "issue", size: { width: 170, height: 60 }, group: "Context" },
  { key: "risk", label: "Risk", type: "risk", size: { width: 170, height: 60 }, group: "Context" },
  { key: "control", label: "Check or approval", type: "control", size: { width: 160, height: 48 }, group: "Context" },
  { key: "metric", label: "Number", type: "metric", size: { width: 140, height: 48 }, group: "Context" },
  { key: "question", label: "To confirm", type: "question", size: { width: 170, height: 60 }, group: "Context" },
  { key: "sticky", label: "Sticky note", type: "sticky", size: { width: 160, height: 120 }, group: "Notes" },
  { key: "text", label: "Text", type: "text", group: "Notes" },
  { key: "image", label: "Image", type: "image", size: { width: 240, height: 180 }, group: "Notes" },
];

export const FLOWS = {
  sequence: { label: "Next step", style: { stroke: "var(--ink)", strokeWidth: 1.8 }, arrow: true },
  message: { label: "Message", style: { stroke: "var(--survey)", strokeWidth: 1.5, strokeDasharray: "7 5" }, arrow: true },
  association: { label: "Note link", style: { stroke: "var(--muted)", strokeWidth: 1.3, strokeDasharray: "2 4" }, arrow: false },
} as const;

export type Flow = keyof typeof FLOWS;
