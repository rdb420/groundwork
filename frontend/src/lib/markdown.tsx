// A deliberately small Markdown renderer for AI drafts: headings, lists, paragraphs, bold,
// and [TO CONFIRM] markers. Renders React elements, never raw HTML.
import type { ReactNode } from "react";

function inline(text: string, key: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\[TO CONFIRM[^\]]*\])/g);
  return parts.map((p, i) => {
    if (p.startsWith("**")) return <strong key={`${key}-${i}`}>{p.slice(2, -2)}</strong>;
    if (p.startsWith("[TO CONFIRM")) return <mark className="confirm" key={`${key}-${i}`}>{p.slice(1, -1)}</mark>;
    return p;
  });
}

export function Markdown({ source }: { source: string }) {
  const out: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  const flush = () => {
    if (!list) return;
    const Tag = list.ordered ? "ol" : "ul";
    out.push(<Tag key={`l${out.length}`}>{list.items.map((t, i) => <li key={i}>{inline(t, `li${i}`)}</li>)}</Tag>);
    list = null;
  };
  source.split("\n").forEach((line, i) => {
    const h = line.match(/^(#{1,4})\s+(.*)/);
    const ul = line.match(/^\s*[-*]\s+(.*)/);
    const ol = line.match(/^\s*\d+[.)]\s+(.*)/);
    if (h) {
      flush();
      const level = Math.min(h[1].length + 1, 5);
      const Tag = `h${level}` as "h2";
      out.push(<Tag key={i}>{inline(h[2], `h${i}`)}</Tag>);
    } else if (ul || ol) {
      const ordered = !!ol;
      if (list && list.ordered !== ordered) flush();
      if (!list) list = { ordered, items: [] };
      list.items.push((ul || ol)![1]);
    } else if (line.trim() === "") {
      flush();
    } else {
      flush();
      out.push(<p key={i}>{inline(line, `p${i}`)}</p>);
    }
  });
  flush();
  return <div className="md">{out}</div>;
}
