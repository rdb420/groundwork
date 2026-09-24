import { describe, expect, it } from "vitest";
import type { Node } from "@xyflow/react";
import { acceptOp, applyOp, isOpen, rejectOp, type Graph, type Op } from "../canvas/ops";

const task = (id: string, x = 0, label = id): Node => ({ id, type: "bpmnTask", position: { x, y: 100 }, width: 150, height: 64, data: { label } });
const base = (): Graph => ({ nodes: [task("a")], edges: [] });
const op = (o: Partial<Op>): Op => ({ id: "op1", op: "add", source: "jev", auto: false, confidence: 0.5, ...o });

describe("applyOp", () => {
  it("lands an auto add as a real element linked after its anchor", () => {
    const g = applyOp(base(), op({ auto: true, ref: "b", kind: "task", label: "Send reminder", after: "a" }));
    const b = g.nodes.find((n) => n.id === "b")!;
    expect(b.data.suggested).toBe(false);
    expect(b.position.x).toBeGreaterThan(150);
    expect(g.edges).toHaveLength(1);
    expect(g.edges[0]).toMatchObject({ source: "a", target: "b" });
    expect(isOpen(g, "op1")).toBe(false);
  });

  it("lands a low-confidence add as a proposal that can be accepted or rejected", () => {
    const g = applyOp(base(), op({ ref: "b", kind: "task", label: "Send reminder", after: "a" }));
    expect(isOpen(g, "op1")).toBe(true);
    const kept = acceptOp(g, "op1");
    expect(kept.nodes.find((n) => n.id === "b")!.data.suggested).toBe(false);
    expect(isOpen(kept, "op1")).toBe(false);
    const dropped = rejectOp(g, "op1");
    expect(dropped.nodes.map((n) => n.id)).toEqual(["a"]);
    expect(dropped.edges).toHaveLength(0);
  });

  it("never removes without a click, even when marked auto", () => {
    const g = applyOp(base(), op({ op: "remove", target: "a", auto: true }));
    expect(g.nodes.map((n) => n.id)).toEqual(["a"]);
    expect(isOpen(g, "op1")).toBe(true);
    expect(acceptOp(g, "op1").nodes).toHaveLength(0);
    expect(rejectOp(g, "op1").nodes.map((n) => n.id)).toEqual(["a"]);
  });

  it("holds a pending rename until accepted", () => {
    const g = applyOp(base(), op({ op: "update", target: "a", changes: { label: "Check bank feed" } }));
    expect(g.nodes[0].data.label).toBe("a");
    expect(acceptOp(g, "op1").nodes[0].data.label).toBe("Check bank feed");
  });

  it("adds an outside party as one pool with a message flow, reusing it the second time", () => {
    let g = applyOp(base(), op({ auto: true, ref: "p1", kind: "external_party", label: "Tenant", after: "a", direction: "in" }));
    g = applyOp(g, op({ id: "op2", auto: true, ref: "p2", kind: "external_party", label: "tenant", after: "a" }));
    expect(g.nodes.filter((n) => n.type === "pool")).toHaveLength(1);
    expect(g.edges.every((e) => (e.data as any).flow === "message")).toBe(true);
  });

  it("ignores changes to elements that no longer exist", () => {
    const g = base();
    expect(applyOp(g, op({ op: "update", target: "gone", changes: { label: "x" } }))).toBe(g);
    expect(applyOp(g, op({ op: "connect", from: "a", to: "gone" }))).toBe(g);
  });
});
