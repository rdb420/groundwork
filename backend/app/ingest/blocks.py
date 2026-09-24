"""The one shape every converter produces and the chunker reads: a list of blocks.

    {"type": "heading", "text": "Arrears", "level": 1, "page": 3}
    {"type": "text", "text": "...", "page": 3}
    {"type": "list", "items": ["...", "..."], "page": 3}
    {"type": "table", "rows": [["Tenant", "Owing"], ["A", "120"]], "caption": "...", "page": 4}
    {"type": "image", "text": "caption or description", "page": 5}
    {"type": "transcript", "text": "...", "start_s": 30.0, "end_s": 34.5}

Pages are 1-based. MinerU's content_list, Markdown, spreadsheets, email and transcripts all map
onto these, so chunking has one input format however the file arrived.
"""
import re
from html.parser import HTMLParser

SKIP = {"header", "footer", "page_number", "aside_text", "page_footnote", "discarded"}


class _TableParser(HTMLParser):
    """Rows of cell text from an HTML table. Spans are ignored; nested tables flatten."""

    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def html_table_rows(html: str) -> list[list[str]]:
    p = _TableParser()
    p.feed(html or "")
    return p.rows


def _joined(v) -> str:
    if isinstance(v, list):
        return " ".join(str(x) for x in v if str(x).strip())
    return str(v or "")


def from_mineru(content_list: list[dict], page_offset: int = 0) -> list[dict]:
    """MinerU content_list blocks to ours. page_idx is 0-based within the task; page_offset adds
    the window start for long PDFs sent in parts."""
    out: list[dict] = []
    for b in content_list or []:
        if not isinstance(b, dict):
            continue
        t = b.get("type", "")
        page = int(b.get("page_idx", 0) or 0) + page_offset + 1
        if t in SKIP:
            continue
        if t == "text":
            text = (b.get("text") or "").strip()
            if not text:
                continue
            level = int(b.get("text_level") or 0)
            out.append({"type": "heading", "text": text, "level": level, "page": page} if level
                       else {"type": "text", "text": text, "page": page})
        elif t == "list":
            items = [str(i).strip() for i in b.get("list_items") or [] if str(i).strip()]
            if items:
                out.append({"type": "list", "items": items, "page": page})
        elif t == "table":
            rows = html_table_rows(b.get("table_body", ""))
            caption = " ".join(x for x in (_joined(b.get("table_caption")), _joined(b.get("table_footnote"))) if x)
            if rows:
                out.append({"type": "table", "rows": rows, "caption": caption, "page": page})
            elif caption:
                out.append({"type": "text", "text": caption, "page": page})
        elif t in ("image", "chart"):
            text = " ".join(x for x in (_joined(b.get(f"{t}_caption")), _joined(b.get(f"{t}_footnote")),
                                        str(b.get("content") or "")) if x.strip())
            if text.strip():
                out.append({"type": "image", "text": text.strip(), "page": page})
        elif t in ("equation", "code"):
            text = str(b.get("text") or b.get("code_body") or "").strip()
            if text:
                out.append({"type": "text", "text": text, "page": page})
    return out


_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


def _pipe_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def from_markdown(md: str) -> list[dict]:
    """Headings, pipe tables, lists and paragraphs from Markdown (or plain text, which has no headings)."""
    out: list[dict] = []
    lines = md.splitlines()
    i = 0
    para: list[str] = []
    items: list[str] = []

    def flush():
        nonlocal para, items
        if para:
            out.append({"type": "text", "text": "\n".join(para).strip()})
        if items:
            out.append({"type": "list", "items": items})
        para, items = [], []

    while i < len(lines):
        line = lines[i]
        h = _HEADING.match(line)
        if h:
            flush()
            out.append({"type": "heading", "text": h.group(2), "level": len(h.group(1))})
        elif "|" in line and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1]):
            flush()
            rows = [_pipe_row(line)]
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(_pipe_row(lines[i]))
                i += 1
            out.append({"type": "table", "rows": rows, "caption": ""})
            continue
        elif re.match(r"^\s*([-*+]|\d+[.)])\s+", line):
            if para:
                out.append({"type": "text", "text": "\n".join(para).strip()})
                para = []
            items.append(re.sub(r"^\s*([-*+]|\d+[.)])\s+", "", line).strip())
        elif not line.strip():
            flush()
        else:
            if items:
                out.append({"type": "list", "items": items})
                items = []
            para.append(line.rstrip())
        i += 1
    flush()
    return [b for b in out if b.get("text", "x").strip() or b.get("items") or b.get("rows")]


def _cell(v: str) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ")


def to_markdown(blocks: list[dict]) -> str:
    """Render blocks back to Markdown, for the stored document.md of files not converted by MinerU."""
    parts: list[str] = []
    for b in blocks:
        t = b.get("type")
        if t == "heading":
            parts.append("#" * max(1, min(6, int(b.get("level") or 1))) + " " + b["text"])
        elif t == "list":
            parts.append("\n".join(f"- {x}" for x in b["items"]))
        elif t == "table":
            rows = b["rows"]
            width = max(len(r) for r in rows)
            rows = [r + [""] * (width - len(r)) for r in rows]
            lines = ["| " + " | ".join(_cell(c) for c in rows[0]) + " |", "|" + "---|" * width]
            lines += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows[1:]]
            if b.get("caption"):
                lines.insert(0, f"*{b['caption']}*")
            parts.append("\n".join(lines))
        elif t == "transcript":
            parts.append(f"[{b.get('start_s', 0):.0f}s] {b['text']}")
        else:
            parts.append(b.get("text", ""))
    return "\n\n".join(p for p in parts if p.strip()) + "\n"
