"""Split a document's blocks into chunks of at most GW_CHUNK_TOKENS tokens (128 by default, the
smallest window of the three embedding models), following the document's own structure:

1. Headings start a new section and never share a chunk with the section before.
2. Each chunk's embedded text starts with its heading breadcrumb ("Lease > Rent > Arrears"),
   capped at 24 tokens with the deepest headings kept, so a short chunk still says what it's about.
3. Paragraphs split on line breaks, then on sentences, then (rarely) at a token boundary.
4. Lines pack into a chunk until the next one wouldn't fit.
5. Tables pack row by row with the header row repeated at the top of every chunk.
6. Page numbers (files) or start and end times (transcripts) carry through.
7. A short trailing chunk joins the one before it in the same section when it fits.
"""
import re
from dataclasses import dataclass, field

from . import tokens

CRUMB_CAP = 24
MIN_TAIL = 24
BOUNDARY = re.compile(r"[.!?][\"')\]]?\s+(?=[\"'(A-Z0-9])")
ABBREVIATIONS = {"e.g", "i.e", "etc", "pty", "no", "mr", "mrs", "ms", "dr", "st", "approx", "vs", "ltd"}


def sentences(text: str) -> list[str]:
    """Split on sentence ends, but not after common abbreviations ("Pty. Ltd.", "e.g.", "No. 4")."""
    out, start = [], 0
    for m in BOUNDARY.finditer(text):
        word = text[start:m.start()].rsplit(None, 1)[-1].lower() if text[start:m.start()].strip() else ""
        if word.rstrip(".") in ABBREVIATIONS:
            continue
        out.append(text[start:m.end()].strip())
        start = m.end()
    tail = text[start:].strip()
    return [x for x in out + [tail] if x]


@dataclass
class Unit:
    text: str
    tokens: int
    page: int | None = None
    start_s: float | None = None
    end_s: float | None = None


@dataclass
class Piece:
    text: str  # the body
    embed_text: str  # breadcrumb + body, what gets embedded
    heading_path: list[str]
    kind: str
    tokens: int  # of embed_text
    page: int | None = None
    page_end: int | None = None
    start_s: float | None = None
    end_s: float | None = None
    units: list[Unit] = field(default_factory=list, repr=False)


def _crumb(parts: list[str]) -> str:
    parts = [p for p in parts if p]
    while len(parts) > 1 and tokens.count(" > ".join(parts)) > CRUMB_CAP:
        parts = parts[1:]
    text = " > ".join(parts)
    if tokens.count(text) > CRUMB_CAP:
        text = tokens.split_at(text, CRUMB_CAP)[0]
    return text


def _split_long(text: str, limit: int) -> list[str]:
    """Sentences, then hard token splits, each at most limit tokens."""
    out: list[str] = []
    for sentence in sentences(text):
        sentence = sentence.strip()
        while sentence:
            if tokens.count(sentence) <= limit:
                out.append(sentence)
                break
            head, sentence = tokens.split_at(sentence, limit)
            if not head:  # a single token longer than the limit can't happen with WordPiece, but never loop
                head, sentence = sentence[:200], sentence[200:]
            out.append(head)
    return out


def _units(text: str, limit: int, **where) -> list[Unit]:
    out = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        pieces = [line] if tokens.count(line) <= limit else _split_long(line, limit)
        out += [Unit(p, tokens.count(p), **where) for p in pieces]
    return out


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(c.replace("\n", " ") for c in cells) + " |"


class _Packer:
    def __init__(self, budget: int):
        self.budget = budget
        self.out: list[Piece] = []

    def _piece(self, units: list[Unit], crumb: str, path: list[str], kind: str, prefix: str) -> Piece:
        body = "\n".join(([prefix] if prefix else []) + [u.text for u in units])
        embed = f"{crumb}\n{body}" if crumb else body
        pages = [u.page for u in units if u.page is not None]
        starts = [u.start_s for u in units if u.start_s is not None]
        ends = [u.end_s for u in units if u.end_s is not None]
        return Piece(body, embed, path, kind, tokens.count(embed), min(pages, default=None), max(pages, default=None),
                     min(starts, default=None), max(ends, default=None), units)

    def emit(self, units: list[Unit], crumb: str, path: list[str], kind: str, prefix: str = "") -> None:
        """Pack units into pieces under the budget. prefix (a table header) repeats in every piece."""
        limit = self.budget - tokens.count(crumb) - tokens.count(prefix)
        groups: list[list[Unit]] = []
        current: list[Unit] = []
        size = 0
        for u in units:
            if u.tokens > limit:  # callers keep units under the limit; this is the safety net
                parts = [Unit(p, tokens.count(p), u.page, u.start_s, u.end_s) for p in _split_long(u.text, limit)]
            else:
                parts = [u]
            for part in parts:
                if current and size + part.tokens > limit:
                    groups.append(current)
                    current, size = [], 0
                current.append(part)
                size += part.tokens
        if current:
            groups.append(current)
        # A short tail joins the group before it, within this section, when both fit.
        if len(groups) >= 2 and sum(u.tokens for u in groups[-1]) < MIN_TAIL \
                and sum(u.tokens for u in groups[-2] + groups[-1]) <= limit:
            groups[-2:] = [groups[-2] + groups[-1]]
        self.out += [self._piece(g, crumb, path, kind, prefix) for g in groups]


def chunk(blocks: list[dict], title: str = "", budget: int = 128) -> list[Piece]:
    packer = _Packer(budget)
    stack: list[tuple[int, str]] = []
    pending: list[Unit] = []
    pending_kind = "text"

    def path() -> list[str]:
        return [h for _, h in stack]

    def crumb(extra: str = "") -> str:
        return _crumb([title] + path() + ([extra] if extra else []))

    def flush_section():
        nonlocal pending
        if pending:
            packer.emit(pending, crumb(), path(), pending_kind)
            pending = []

    def switch(kind: str):
        """Text and transcript lines don't share a chunk."""
        nonlocal pending_kind
        if kind != pending_kind:
            flush_section()
            pending_kind = kind

    for b in blocks:
        t = b.get("type")
        page = b.get("page")
        if t == "heading":
            flush_section()
            level = int(b.get("level") or 1)
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, " ".join(b["text"].split())))
            continue
        limit = budget - tokens.count(crumb())
        if t in ("text", None):
            switch("text")
            pending += _units(b.get("text", ""), limit, page=page)
        elif t == "list":
            switch("text")
            for item in b.get("items", []):
                pending += _units(f"- {item}", limit, page=page)
        elif t == "transcript":
            switch("transcript")
            pending += _units(b.get("text", ""), limit, start_s=b.get("start_s"), end_s=b.get("end_s"))
        elif t == "image":
            flush_section()
            text = f"[Image] {b.get('text', '')}".strip()
            packer.emit(_units(text, budget - tokens.count(crumb()), page=page), crumb(), path(), "image")
        elif t == "table":
            flush_section()
            rows = b.get("rows") or []
            if not rows:
                continue
            table_crumb = crumb(b.get("caption", ""))
            header = _row(rows[0])
            if tokens.count(table_crumb) + tokens.count(header) > budget // 2:
                header = ""  # a very wide header would leave no room; rows then carry column: value text
            body_limit = budget - tokens.count(table_crumb) - tokens.count(header)
            units = []
            for r in rows[1:] if header else rows:
                text = _row(r)
                if tokens.count(text) > body_limit:
                    labels = rows[0] if header or len(rows) > 1 else [""] * len(r)
                    text = "\n".join(f"{(labels[i] if i < len(labels) else '') or f'Column {i + 1}'}: {c}"
                                     for i, c in enumerate(r) if c)
                    units += _units(text, body_limit, page=page)
                else:
                    units.append(Unit(text, tokens.count(text), page=page))
            packer.emit(units, table_crumb, path(), "table", header)
    flush_section()
    return packer.out
