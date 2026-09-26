// BPMN and whiteboard elements for the canvas. Every node carries its meaning in `type`
// and `data`, so the server can read the map as a process, not just as shapes.
import { createContext, useContext, useState } from "react";
import { Handle, NodeResizer, Position, useReactFlow, type NodeProps } from "@xyflow/react";
import { POOL_HANDLES } from "./ops";
import { Input, SuggestBar, Tag, TextArea, cx } from "../ui";

type Pending = { opId: string; source?: string; reason?: string; remove?: boolean; changes?: { label?: string; kind?: string; lane_id?: string; new_lane?: string } };
type D = {
  label?: string; gatewayType?: string; taskKind?: string; dataKind?: string; artifactId?: string; system?: string;
  suggested?: boolean; opId?: string; source?: string; reason?: string; pending?: Pending; tags?: string[];
};

// Selection and proposal state, on the element that carries the border.
const state = (d: D, selected?: boolean) => cx(d.suggested && "gw-suggested", d.pending && "gw-pending", selected && "gw-sel");

// Accept and reject go through the op engine so connected edges follow their element.
export const ProposalContext = createContext<{ accept: (opId: string) => void; reject: (opId: string) => void } | null>(null);

function Handles() {
  return (
    <>
      <Handle type="source" position={Position.Top} id="t" />
      <Handle type="source" position={Position.Right} id="r" />
      <Handle type="source" position={Position.Bottom} id="b" />
      <Handle type="source" position={Position.Left} id="l" />
    </>
  );
}

function Label({ id, value, placeholder, multiline }: { id: string; value?: string; placeholder: string; multiline?: boolean }) {
  const { updateNodeData } = useReactFlow();
  const [editing, setEditing] = useState(false);
  if (editing) {
    const common = {
      className: "nodrag gw-node-input",
      autoFocus: true,
      defaultValue: value || "",
      onBlur: (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => { updateNodeData(id, { label: e.target.value }); setEditing(false); },
      onKeyDown: (e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        if (e.key === "Escape" || (e.key === "Enter" && !multiline)) (e.target as HTMLElement).blur();
      },
    };
    return multiline ? <TextArea {...common} /> : <Input {...common} />;
  }
  return (
    <span className={cx("gw-node-label", !value && "empty")} onDoubleClick={() => setEditing(true)} title="Double-click to edit">
      {value || placeholder}
    </span>
  );
}

function describeChange(p: Pending) {
  if (p.remove) return "Remove this?";
  const c = p.changes || {};
  const parts = [c.label !== undefined && `rename to "${c.label}"`, c.kind && `make it a ${c.kind.replace("_", " ")}`, (c.lane_id || c.new_lane) && `move to ${c.new_lane ? `new lane "${c.new_lane}"` : "another lane"}`].filter(Boolean);
  return parts.length ? `Proposed: ${parts.join(", ")}` : "Proposed change";
}

function Suggested({ id, data }: { id: string; data: D }) {
  const { updateNodeData, deleteElements } = useReactFlow();
  const ops = useContext(ProposalContext);
  const who = (src?: string) => (src === "review" ? "Reviewer" : src === "jev" ? "Heard" : "Suggested");
  if (data.pending) {
    const p = data.pending;
    return <SuggestBar className="nodrag" who={who(p.source)} change={describeChange(p)} title={p.reason}
      onKeep={() => ops?.accept(p.opId)} onDrop={() => ops?.reject(p.opId)} />;
  }
  if (!data.suggested) return null;
  const keep = () => (data.opId && ops ? ops.accept(data.opId) : updateNodeData(id, { suggested: false }));
  const drop = () => (data.opId && ops ? ops.reject(data.opId) : deleteElements({ nodes: [{ id }] }));
  return <SuggestBar className="nodrag" who={who(data.source)} title={data.reason} onKeep={keep} onDrop={drop} />;
}

function Tags({ tags }: { tags?: string[] }) {
  if (!tags?.length) return null;
  return <div className="gw-tags">{tags.map((t) => <Tag key={t} kind={t === "workaround" || t === "issue" ? t : "plain"}>{t}</Tag>)}</div>;
}

export function EventNode({ id, data, type, selected }: NodeProps) {
  const d = data as D;
  const cls = type === "bpmnStart" ? "start" : type === "bpmnEnd" ? "end" : "intermediate";
  return (
    <div className={cx("gw-bpmn-event", cls)}>
      <Suggested id={id} data={d} />
      <div className={cx("ring", state(d, selected))} />
      <Handles />
      <div className="gw-under"><Label id={id} value={d.label} placeholder={cls === "start" ? "What starts it?" : cls === "end" ? "Outcome" : "Event"} /></div>
    </div>
  );
}

// Small BPMN-style task markers drawn in the top-left corner.
const TASK_ICON: Record<string, React.ReactNode> = {
  user: <svg viewBox="0 0 16 16" width="15" height="15"><circle cx="8" cy="5" r="3" fill="none" stroke="currentColor" strokeWidth="1.4" /><path d="M2.5 15c0-3.5 2.5-5.5 5.5-5.5s5.5 2 5.5 5.5" fill="none" stroke="currentColor" strokeWidth="1.4" /></svg>,
  rule: <svg viewBox="0 0 16 16" width="15" height="15"><rect x="1.5" y="2.5" width="13" height="11" fill="none" stroke="currentColor" strokeWidth="1.3" /><path d="M1.5 6h13M1.5 9.5h13M6 2.5v11" stroke="currentColor" strokeWidth="1.1" /></svg>,
  manual: <svg viewBox="0 0 16 16" width="15" height="15"><path d="M4 14V7.5a1.2 1.2 0 0 1 2.4 0V9M6.4 9V3.5a1.2 1.2 0 0 1 2.4 0V8.5M8.8 8.5V4.5a1.2 1.2 0 0 1 2.4 0V9M11.2 9V6.5a1.2 1.2 0 0 1 2.4 0V11c0 2-1.5 3-3.5 3H7" fill="none" stroke="currentColor" strokeWidth="1.3" /></svg>,
  system: <svg viewBox="0 0 16 16" width="15" height="15"><circle cx="8" cy="8" r="2.4" fill="none" stroke="currentColor" strokeWidth="1.4" /><path d="M8 1.5v2.2M8 12.3v2.2M1.5 8h2.2M12.3 8h2.2M3.4 3.4l1.6 1.6M11 11l1.6 1.6M3.4 12.6L5 11M11 5l1.6-1.6" stroke="currentColor" strokeWidth="1.4" /></svg>,
};

export function TaskNode({ id, data, type, selected }: NodeProps) {
  const d = data as D;
  return (
    <div className={cx("gw-bpmn-task", d.taskKind === "manual" && "manual", !!d.taskKind && d.taskKind in TASK_ICON && "has-icon", state(d, selected))}>
      <NodeResizer isVisible={!!selected} minWidth={110} minHeight={54} />
      <Suggested id={id} data={d} />
      {d.taskKind && TASK_ICON[d.taskKind] && <span className="gw-task-icon" aria-hidden="true">{TASK_ICON[d.taskKind]}</span>}
      <Label id={id} value={d.label} placeholder="What happens?" multiline />
      {type === "bpmnSubprocess" && <span className="plus" aria-hidden="true">+</span>}
      <Tags tags={d.tags} />
      <Handles />
    </div>
  );
}

export function GatewayNode({ id, data, selected }: NodeProps) {
  const d = data as D;
  const mark = d.gatewayType === "parallel" ? "+" : d.gatewayType === "inclusive" ? "○" : "×";
  return (
    <div className="gw-bpmn-gateway">
      <Suggested id={id} data={d} />
      <div className={cx("diamond", state(d, selected))}><span>{mark}</span></div>
      <Handles />
      <div className="gw-under"><Label id={id} value={d.label} placeholder="Decision?" /></div>
    </div>
  );
}

export function DataNode({ id, data }: NodeProps) {
  const d = data as D;
  const store = d.dataKind === "store";
  return (
    <div className="gw-bpmn-data">
      <Suggested id={id} data={d} />
      <svg width="44" height="52" viewBox="0 0 44 52" aria-hidden="true">
        {store ? (
          <g fill="var(--paper)" stroke="currentColor" strokeWidth="2">
            <path d="M3 10v32c0 5 38 5 38 0V10" /><ellipse cx="22" cy="10" rx="19" ry="6" />
            <path d="M3 17c0 5 38 5 38 0" fill="none" />
          </g>
        ) : (
          <path d="M3 2h26l12 12v36H3z M29 2v12h12" fill="var(--paper)" stroke="currentColor" strokeWidth="2" />
        )}
      </svg>
      <Handles />
      <div className="gw-under"><Label id={id} value={d.label} placeholder={store ? "Where is it kept?" : "Which document?"} /></div>
    </div>
  );
}

export function LaneNode({ id, data, selected }: NodeProps) {
  const d = data as D;
  return (
    <div className={cx("gw-lane", selected && "sel")}>
      <NodeResizer isVisible={!!selected} minWidth={300} minHeight={120} />
      <div className="gw-lane-head"><Label id={id} value={d.label} placeholder="Who does this?" /></div>
    </div>
  );
}

export function StickyNode({ id, data, selected }: NodeProps) {
  const d = data as D;
  return (
    <div className={cx("gw-sticky", state(d))}>
      <NodeResizer isVisible={!!selected} minWidth={120} minHeight={90} />
      <Suggested id={id} data={d} />
      <Label id={id} value={d.label} placeholder="Double-click to write a note" multiline />
      <Handles />
    </div>
  );
}

export function TextNode({ id, data, selected }: NodeProps) {
  const d = data as D;
  return (
    <div className={cx("gw-freetext", selected && "sel")}>
      <Label id={id} value={d.label} placeholder="Text" multiline />
    </div>
  );
}

export function ImageNode({ data, selected }: NodeProps) {
  const d = data as D;
  return (
    <div className={cx("gw-imagenode", selected && "sel")}>
      <NodeResizer isVisible={!!selected} minWidth={80} minHeight={60} keepAspectRatio />
      {d.artifactId ? <img src={`/api/artifacts/${d.artifactId}/file`} alt={d.label || "Uploaded image"} draggable={false} /> : <span>Uploading…</span>}
      <Handles />
    </div>
  );
}

// People, systems, problems and the other things that surround the steps. One component,
// styled per kind, so the canvas stays consistent and the list is easy to extend.
const CONTEXT_META: Record<string, { mark: string; placeholder: string }> = {
  stakeholder: { mark: "Person", placeholder: "Who?" },
  application: { mark: "System", placeholder: "Which system?" },
  workaround: { mark: "Workaround", placeholder: "What do people do instead?" },
  issue: { mark: "Issue", placeholder: "What goes wrong?" },
  control: { mark: "Check", placeholder: "What is checked or approved?" },
  metric: { mark: "Number", placeholder: "How many, how often, how long?" },
  question: { mark: "To confirm", placeholder: "What needs confirming?" },
  risk: { mark: "Risk", placeholder: "What could go seriously wrong?" },
};

// An outside party (tenant, bank, contractor) as a collapsed pool: a band across the map, linked
// to steps by message flows. Handles along the bottom let each message flow meet it above its step.
export function PoolNode({ id, data, selected }: NodeProps) {
  const d = data as D;
  return (
    <div className={cx("gw-pool", d.suggested && "gw-suggested", selected && "sel")}>
      <NodeResizer isVisible={!!selected} minWidth={300} minHeight={40} />
      <Suggested id={id} data={d} />
      <span className="gw-pool-mark">Outside party</span>
      <Label id={id} value={d.label} placeholder="Who, outside the business?" />
      {Array.from({ length: POOL_HANDLES }, (_, i) => (
        <Handle key={i} type="source" position={Position.Bottom} id={`b${i}`} style={{ left: `${((i + 0.5) / POOL_HANDLES) * 100}%` }} />
      ))}
    </div>
  );
}

// An area of work nobody can yet describe as ordered steps (a BPMN ad hoc sub-process).
// Better an honest boundary than an invented sequence.
export function AdhocNode({ id, data, selected }: NodeProps) {
  const d = data as D;
  return (
    <div className={cx("gw-adhoc", state(d, selected))}>
      <NodeResizer isVisible={!!selected} minWidth={160} minHeight={80} />
      <Suggested id={id} data={d} />
      <span className="gw-ctx-mark">Unclear</span>
      <Label id={id} value={d.label} placeholder="What part of the work is unclear?" multiline />
      <span className="tilde" aria-hidden="true">~</span>
      <Handles />
    </div>
  );
}

export function ContextNode({ id, data, type, selected }: NodeProps) {
  const d = data as D;
  const meta = CONTEXT_META[type as string] ?? { mark: "", placeholder: "" };
  return (
    <div className={cx("gw-ctx", type, state(d, selected))}>
      <NodeResizer isVisible={!!selected} minWidth={110} minHeight={40} />
      <Suggested id={id} data={d} />
      <span className="gw-ctx-mark">{meta.mark}</span>
      <Label id={id} value={d.label} placeholder={meta.placeholder} multiline />
      <Handles />
    </div>
  );
}

export const nodeTypes = {
  bpmnStart: EventNode, bpmnEnd: EventNode, bpmnIntermediate: EventNode,
  bpmnTask: TaskNode, bpmnSubprocess: TaskNode, bpmnGateway: GatewayNode, bpmnData: DataNode,
  lane: LaneNode, sticky: StickyNode, text: TextNode, image: ImageNode,
  stakeholder: ContextNode, application: ContextNode, workaround: ContextNode, issue: ContextNode,
  control: ContextNode, metric: ContextNode, question: ContextNode, risk: ContextNode,
  pool: PoolNode, adhoc: AdhocNode,
};

export const KNOWN_TYPES = new Set(Object.keys(nodeTypes));
