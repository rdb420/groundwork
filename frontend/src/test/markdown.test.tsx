import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Markdown } from "../lib/markdown";

describe("Markdown", () => {
  it("renders headings, lists and confirm markers", () => {
    const html = renderToStaticMarkup(<Markdown source={"# SOP\n\n1. Check **feed**\n2. Send [TO CONFIRM: who sends]"} />);
    expect(html).toContain("<h2>SOP</h2>");
    expect(html).toContain("<ol>");
    expect(html).toContain("<strong>feed</strong>");
    expect(html).toContain('<mark class="confirm">TO CONFIRM: who sends</mark>');
  });

  it("never passes model output through as HTML", () => {
    const html = renderToStaticMarkup(<Markdown source={'<img src=x onerror="alert(1)"> and <script>x</script>'} />);
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<script");
  });
});
