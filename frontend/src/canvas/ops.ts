// Apply, accept and reject map changes proposed by the live interpreter, the session reviewer or
// the view combiner. Pure functions over nodes and edges. Every proposed element or edge carries
// data.opId, so the feed, the node bars and "Accept all" can all find it again.
import { MarkerType, type Edge, type Node } from "@xyflow/react";
import { FLOW_KINDS, NODE_FOR_KIND, kindOf, type Kind } from "./kinds";
import { FLOWS } from "./palette";

export type Op = {
  id: string;
  op: "add" | "update" | "connect" | "remove";
  source: "jev" | "review" | "combine";
  auto: boolean;
  confidence: number | null;
  reason?: string;
  evidence?: string;
  ref?: string; kind?: Kind; label?: string; after?: string | null; tags?: string[];
  lane_id?: string; new_lane?: string;
  party?: string; direction?: "in" | "out"; relation?: "cause";
  target?: string; changes?: { label?: string; kind?: Kind; lane_id?: string; new_lane?: string };
  from?: string; to?: string; flow?: "sequence" | "message";
};

export type Graph = { nodes: Node[]; edges: Edge[] };
export const POOL_HANDLES = 12;
const W = (n: Node) => (n.width as number) || (n.measured?.width as number) || 150;
const Hh = (n: Node) => (n.height as number) || (n.measured?.height as number) || 60;
const rid = () => Math.random().toString(36).slice(2, 8);

export function edgeStyle(flow: keyof typeof FLOWS, suggested = false) {
  const f = FLOWS[flow];
  return {
    type: "smoothstep",
    style: { ...f.style, ...(suggested ? { strokeDasharray: "6 4", stroke: "var(--survey)" } : {}) },
    markerEnd: f.arrow ? { type: flow === "message" ? MarkerType.Arrow : MarkerType.ArrowClosed, color: "currentColor" } : undefined,
  };
}

const isBand = (n: Node) => n.type === "lane" || n.type === "pool";

function overlaps(nodes: Node[], x: number, y: number, w: number, h: number) {
  return nodes.some((n) => !isBand(n) && x < n.position.x + W(n) && x + w > n.position.x && y < n.position.y + Hh(n) && y + h > n.position.y);
}

function laneCentreY(lane: Node, h: number) {
  return lane.position.y + Hh(lane) / 2 - h / 2;
}

function extentRight(g: Graph) {
  return Math.max(900, ...g.nodes.filter((n) => !isBand(n)).map((n) => n.position.x + W(n) + 80));
}

function ensureLane(g: Graph, label: string, pending = false, meta = {}): { graph: Graph; lane: Node } {
  const existing = g.nodes.find((n) => n.type === "lane" && String(n.data?.label || "").toLowerCase() === label.toLowerCase());
  if (existing) return { graph: g, lane: existing };
  const lanes = g.nodes.filter((n) => n.type === "lane");
  const y = lanes.length ? Math.max(...lanes.map((l) => l.position.y + Hh(l))) + 16
    : Math.max(0, ...g.nodes.filter((n) => n.type !== "pool").map((n) => n.position.y + Hh(n) + 40));
  const lane: Node = { id: `lane-${rid()}`, type: "lane", position: { x: Math.min(0, ...lanes.map((l) => l.position.x)), y }, width: extentRight(g), height: 200, zIndex: -1, data: { label, ...(pending ? { ...meta, suggested: true } : {}) } };
  return { graph: { ...g, nodes: [...g.nodes, lane] }, lane };
}

/** Outside parties sit as collapsed pools above everything else, one band each. */
function ensurePool(g: Graph, label: string, pending = false, meta = {}, id?: string): { graph: Graph; pool: Node; created: boolean } {
  const existing = g.nodes.find((n) => n.type === "pool" && String(n.data?.label || "").toLowerCase() === label.toLowerCase());
  if (existing) return { graph: g, pool: existing, created: false };
  const others = g.nodes.filter((n) => n.type !== "pool");
  const pools = g.nodes.filter((n) => n.type === "pool");
  const top = Math.min(0, ...others.map((n) => n.position.y));
  const y = (pools.length ? Math.min(...pools.map((p) => p.position.y)) : top - 40) - 56 - 24;
  const pool: Node = { id: id || `pool-${rid()}`, type: "pool", position: { x: Math.min(0, ...others.map((n) => n.position.x)), y }, width: extentRight(g), height: 56, zIndex: -1, data: { label, ...meta, suggested: pending } };
  return { graph: { ...g, nodes: [...g.nodes, pool] }, pool, created: true };
}

function poolHandle(pool: Node, node: Node) {
  const cx = node.position.x + W(node) / 2;
  const i = Math.round(((cx - pool.position.x) / W(pool)) * POOL_HANDLES - 0.5);
  return `b${Math.max(0, Math.min(POOL_HANDLES - 1, i))}`;
}

function messageEdge(pool: Node, node: Node, direction: "in" | "out", opId: string, pending: boolean): Edge {
  const h = poolHandle(pool, node);
  const ends = direction === "in"
    ? { source: pool.id, sourceHandle: h, target: node.id, targetHandle: "t" }
    : { source: node.id, sourceHandle: "t", target: pool.id, targetHandle: h };
  return { id: `m-${opId}-${rid()}`, ...ends, data: { flow: "message", opId, suggested: pending }, ...edgeStyle("message", pending) } as Edge;
}

function place(g: Graph, kind: Kind, size: { width: number; height: number }, anchor?: Node, lane?: Node, cause = false) {
  let x: number, y: number;
  if (cause && anchor) {
    // A cause sits beside the issue it explains, away from the steps.
    for (let i = 0; i < 10; i++) {
      const cx = anchor.position.x + (i + 1) * (size.width + 30);
      if (!overlaps(g.nodes, cx, anchor.position.y, size.width, size.height)) return { x: cx, y: anchor.position.y };
    }
    return { x: anchor.position.x + size.width + 30, y: anchor.position.y - size.height - 30 };
  }
  if (anchor && FLOW_KINDS.has(kind)) {
    x = anchor.position.x + W(anchor) + 70;
    y = anchor.position.y + Hh(anchor) / 2 - size.height / 2;
  } else if (anchor) {
    // Context sits above or below the element it describes, alternating, then spreading right.
    const above = anchor.position.y - size.height - 50;
    const below = anchor.position.y + Hh(anchor) + 50;
    for (let i = 0; i < 12; i++) {
      const cx = anchor.position.x + Math.floor(i / 2) * (size.width + 20);
      const cy = i % 2 === 0 ? above : below;
      if (!overlaps(g.nodes, cx, cy, size.width, size.height)) return { x: cx, y: cy };
    }
    x = anchor.position.x;
    y = above;
  } else {
    const inLane = g.nodes.filter((n) => !isBand(n) && (!lane || (n.position.y >= lane.position.y && n.position.y <= lane.position.y + Hh(lane))));
    x = inLane.length ? Math.max(...inLane.map((n) => n.position.x + W(n))) + 70 : (lane ? lane.position.x + 70 : 80);
    y = lane ? laneCentreY(lane, size.height) : 120;
  }
  if (lane && FLOW_KINDS.has(kind)) y = laneCentreY(lane, size.height);
  for (let i = 0; i < 8 && overlaps(g.nodes, x, y, size.width, size.height); i++) {
    if (FLOW_KINDS.has(kind)) y += size.height + 30; else x += size.width + 20;
  }
  return { x, y };
}

/** Context attaches to steps, not to other context. If the model points at a note, a person or an
 * issue, follow its link back to the step it belongs to. Causes are the exception: a cause attaches
 * to the issue it explains, so chains of causes survive. */
function flowAnchor(g: Graph, node: Node | undefined, keep: boolean): Node | undefined {
  if (!node || keep || FLOW_KINDS.has(kindOf(node))) return node;
  const linked = g.edges.filter((e) => e.source === node.id || e.target === node.id)
    .map((e) => g.nodes.find((n) => n.id === (e.source === node.id ? e.target : e.source)))
    .find((n) => n && FLOW_KINDS.has(kindOf(n)));
  return linked ?? node;
}

function applyChanges(g: Graph, id: string, changes: NonNullable<Op["changes"]>): Graph {
  let graph = g;
  let lane: Node | undefined;
  if (changes.new_lane) ({ graph, lane } = ensureLane(graph, changes.new_lane));
  else if (changes.lane_id) lane = graph.nodes.find((n) => n.id === changes.lane_id);
  return {
    ...graph,
    nodes: graph.nodes.map((n) => {
      if (n.id !== id) return n;
      let next: Node = { ...n, data: { ...n.data } };
      if (changes.label !== undefined) next.data.label = changes.label;
      if (changes.kind) {
        const spec = NODE_FOR_KIND[changes.kind];
        const { taskKind: _t, gatewayType: _g, dataKind: _d, ...rest } = next.data as any;
        next = { ...next, type: spec.type, data: { ...rest, ...(spec.data || {}) }, ...(spec.size || {}) };
      }
      if (lane) next.position = { ...next.position, y: laneCentreY(lane, Hh(next)) };
      return next;
    }),
  };
}

/** Put an op on the canvas. Auto ops land as real elements; the rest land as proposals. */
export function applyOp(g: Graph, op: Op): Graph {
  const pending = !op.auto;
  const meta = { opId: op.id, source: op.source, reason: op.reason, confidence: op.confidence };
  if (op.op === "add" && op.kind === "external_party") {
    const { graph, pool, created } = ensurePool(g, op.label || "Outside party", pending, meta, op.ref);
    const anchor = flowAnchor(graph, op.after ? graph.nodes.find((n) => n.id === op.after) : undefined, false);
    let out = graph;
    if (!created && op.ref && op.ref !== pool.id) {
      // The party is already on the map: point later references to this ref at the existing pool.
      out = { ...out, nodes: out.nodes.map((n) => (n.id === pool.id ? { ...n, data: { ...n.data, aliases: [...((n.data as any).aliases || []), op.ref] } } : n)) };
    }
    if (anchor) out = { ...out, edges: [...out.edges, messageEdge(pool, anchor, op.direction || "in", op.id, pending)] };
    return out;
  }
  if (op.op === "add" && op.kind) {
    const spec = NODE_FOR_KIND[op.kind];
    const size = spec.size || { width: 50, height: 50 };
    let graph = g;
    let lane: Node | undefined;
    if (op.new_lane) ({ graph, lane } = ensureLane(graph, op.new_lane, pending, meta));
    else if (op.lane_id) lane = graph.nodes.find((n) => n.id === op.lane_id);
    const cause = op.relation === "cause";
    const anchor = flowAnchor(graph, op.after ? findNode(graph, op.after) : undefined, cause);
    const pos = place(graph, op.kind, size, anchor, lane, cause);
    const node: Node = {
      id: op.ref || `n${op.id}`, type: spec.type, position: pos, ...(spec.size || {}), ...(spec.zIndex !== undefined ? { zIndex: spec.zIndex } : {}),
      data: { label: op.label || "", ...(spec.data || {}), ...(op.tags?.length ? { tags: op.tags } : {}), ...meta, suggested: pending },
    };
    const edges = [...graph.edges];
    if (anchor) {
      if (cause) {
        edges.push({ id: `e-${op.id}`, source: node.id, target: anchor.id, sourceHandle: "l", targetHandle: "r", label: "causes", data: { flow: "association", opId: op.id, suggested: pending }, ...edgeStyle("association", pending) } as Edge);
      } else {
        const flow = FLOW_KINDS.has(op.kind) ? "sequence" : "association";
        const handles = flow === "sequence"
          ? { source: anchor.id, target: node.id, sourceHandle: "r", targetHandle: "l" }
          : pos.y < anchor.position.y
            ? { source: node.id, target: anchor.id, sourceHandle: "b", targetHandle: "t" }
            : { source: node.id, target: anchor.id, sourceHandle: "t", targetHandle: "b" };
        edges.push({ id: `e-${op.id}`, ...handles, data: { flow, opId: op.id, suggested: pending }, ...edgeStyle(flow, pending) } as Edge);
      }
    }
    let out: Graph = { nodes: [...graph.nodes, node], edges };
    if (op.party) {
      const { graph: withPool, pool } = ensurePool(out, op.party, pending, meta);
      out = { ...withPool, edges: [...withPool.edges, messageEdge(pool, node, op.direction || "in", op.id, pending)] };
    }
    return out;
  }
  if (op.op === "update" && op.target && op.changes) {
    if (!g.nodes.some((n) => n.id === op.target)) return g;
    if (!pending) return applyChanges(g, op.target, op.changes);
    return { ...g, nodes: g.nodes.map((n) => (n.id === op.target ? { ...n, data: { ...n.data, pending: { ...meta, changes: op.changes } } } : n)) };
  }
  if (op.op === "connect" && op.from && op.to) {
    const a = findNode(g, op.from), b = findNode(g, op.to);
    if (!a || !b || a.id === b.id) return g;
    if (g.edges.some((e) => e.source === a.id && e.target === b.id)) return g;
    if (a.type === "pool" || b.type === "pool") {
      const [pool, node, dir] = a.type === "pool" ? [a, b, "in" as const] : [b, a, "out" as const];
      return { ...g, edges: [...g.edges, messageEdge(pool, node, dir, op.id, pending)] };
    }
    const flow = op.flow === "message" ? "message" : FLOW_KINDS.has(kindOf(a)) && FLOW_KINDS.has(kindOf(b)) ? "sequence" : "association";
    return { ...g, edges: [...g.edges, { id: `e-${op.id}`, source: a.id, target: b.id, sourceHandle: "r", targetHandle: "l", label: (op as any).label || undefined, data: { flow, opId: op.id, suggested: pending }, ...edgeStyle(flow, pending) } as Edge] };
  }
  if (op.op === "remove" && op.target) {
    return { ...g, nodes: g.nodes.map((n) => (n.id === op.target ? { ...n, data: { ...n.data, pending: { ...meta, remove: true } } } : n)) };
  }
  return g;
}

function findNode(g: Graph, id: string): Node | undefined {
  return g.nodes.find((n) => n.id === id) ?? g.nodes.find((n) => ((n.data as any)?.aliases || []).includes(id));
}

/** Make a proposal real. */
export function acceptOp(g: Graph, opId: string): Graph {
  let graph = g;
  for (const n of g.nodes) {
    const p = (n.data as any)?.pending;
    if (p?.opId === opId) {
      if (p.remove) {
        return { nodes: graph.nodes.filter((x) => x.id !== n.id), edges: graph.edges.filter((e) => e.source !== n.id && e.target !== n.id) };
      }
      graph = applyChanges(graph, n.id, p.changes);
      graph = { ...graph, nodes: graph.nodes.map((x) => (x.id === n.id ? { ...x, data: { ...x.data, pending: undefined } } : x)) };
    }
  }
  return {
    nodes: graph.nodes.map((n) => ((n.data as any)?.opId === opId ? { ...n, data: { ...n.data, suggested: false } } : n)),
    edges: graph.edges.map((e) => ((e.data as any)?.opId === opId ? { ...e, data: { ...e.data, suggested: false }, ...edgeStyle(((e.data as any).flow || "sequence") as any, false) } : e)),
  };
}

/** Throw a proposal away. Auto-applied elements are left alone; delete those on the canvas. */
export function rejectOp(g: Graph, opId: string): Graph {
  const drop = new Set(g.nodes.filter((n) => (n.data as any)?.opId === opId && (n.data as any)?.suggested).map((n) => n.id));
  return {
    nodes: g.nodes.filter((n) => !drop.has(n.id)).map((n) => ((n.data as any)?.pending?.opId === opId ? { ...n, data: { ...n.data, pending: undefined } } : n)),
    edges: g.edges.filter((e) => !drop.has(e.source) && !drop.has(e.target) && !((e.data as any)?.opId === opId && (e.data as any)?.suggested)),
  };
}

export function isOpen(g: Graph, opId: string): boolean {
  return g.nodes.some((n) => ((n.data as any)?.opId === opId && (n.data as any)?.suggested) || (n.data as any)?.pending?.opId === opId)
    || g.edges.some((e) => (e.data as any)?.opId === opId && (e.data as any)?.suggested);
}
