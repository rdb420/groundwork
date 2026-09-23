import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { FLOW_KINDS, KIND_LABEL, NODE_FOR_KIND } from "../canvas/kinds";

// CLAUDE.md: kinds.ts mirrors backend/app/live/vocabulary.py. This keeps the two in step.
const vocab = readFileSync(fileURLToPath(new URL("../../../backend/app/live/vocabulary.py", import.meta.url)), "utf8");
const keysOf = (block: string) => {
  const body = vocab.split(`${block}: dict[str, str] = {`)[1].split("\n}")[0];
  return [...body.matchAll(/^\s{4}"([a-z_]+)":/gm)].map((m) => m[1]);
};

describe("kinds", () => {
  it("matches the backend vocabulary", () => {
    const flow = keysOf("FLOW_KINDS");
    const context = keysOf("CONTEXT_KINDS");
    expect(new Set(Object.keys(NODE_FOR_KIND))).toEqual(new Set([...flow, ...context]));
    expect(new Set(Object.keys(KIND_LABEL))).toEqual(new Set([...flow, ...context]));
    // "unclear" is a context kind to the decision model but sits in the flow on the canvas.
    expect(new Set(FLOW_KINDS)).toEqual(new Set([...flow, "unclear"]));
  });
});
