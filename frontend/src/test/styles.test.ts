import { readdirSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const read = (rel: string) => readFileSync(new URL(rel, import.meta.url), "utf8");
const TOKENS = new URL("../../design-system/tokens/", import.meta.url);
const designCss = readdirSync(TOKENS).map((f) => readFileSync(new URL(f, TOKENS), "utf8")).join("\n");
const localCss = read("../styles.css");

function sources(dir: URL): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? sources(new URL(`${e.name}/`, dir)) : e.name.endsWith(".tsx") ? [readFileSync(new URL(e.name, dir), "utf8")] : []);
}

describe("styles", () => {
  it("uses design-system colour tokens, not hex values", () => {
    const body = localCss.replace(/\/\*[\s\S]*?\*\//g, "");
    expect(body.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).toEqual([]);
  });

  it("defines every gw- class the components use", () => {
    const defined = new Set([...(designCss + localCss).matchAll(/\.(gw-[\w-]+)/g)].map((m) => m[1]));
    const used = new Set(sources(new URL("../", import.meta.url))
      .flatMap((src) => src.split("\n").filter((l) => /className|cx\(/.test(l)))
      .flatMap((l) => [...l.matchAll(/\bgw-[a-z][\w-]*/g)].map((m) => m[0])));
    expect([...used].filter((c) => !defined.has(c))).toEqual([]);
  });
});
