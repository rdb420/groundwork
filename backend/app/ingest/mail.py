"""Saved emails (.eml): the headers people care about, the body as text, and a list of
attachments. Attachments are converted one level deep by the caller."""
import email
import re
from email import policy
from email.message import EmailMessage
from html.parser import HTMLParser
from pathlib import Path


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("p", "br", "div", "tr", "li", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    p = _Text()
    p.feed(html)
    return re.sub(r"\n{3,}", "\n\n", "".join(p.parts)).strip()


def read_eml(path: Path) -> tuple[list[dict], list[tuple[str, bytes]]]:
    """(blocks, attachments as (filename, bytes))."""
    msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
    assert isinstance(msg, EmailMessage)
    subject = str(msg.get("subject", "") or "(no subject)")
    out: list[dict] = [{"type": "heading", "text": f"Email: {subject}", "level": 1}]
    meta = [f"{k}: {msg.get(k)}" for k in ("From", "To", "Cc", "Date") if msg.get(k)]
    if meta:
        out.append({"type": "list", "items": meta})
    body = msg.get_body(preferencelist=("plain", "html"))
    if body is not None:
        content = body.get_content()
        text = html_to_text(content) if body.get_content_type() == "text/html" else str(content)
        for para in re.split(r"\n\s*\n", text):
            if para.strip():
                out.append({"type": "text", "text": para.strip()})
    attachments = []
    for part in msg.iter_attachments():
        name = part.get_filename() or "attachment"
        data = part.get_payload(decode=True)
        if isinstance(data, bytes):
            attachments.append((name, data))
    if attachments:
        out.append({"type": "heading", "text": "Attachments", "level": 2})
        out.append({"type": "list", "items": [n for n, _ in attachments]})
    return out, attachments
