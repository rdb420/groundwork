"""Pick a converter by file type and turn the file into blocks plus Markdown.

    pdf, images, docx, pptx      MinerU
    doc, ppt, odt, rtf, xls, ods Gotenberg to PDF, then MinerU
    xlsx, xlsm, csv, tsv         native tables
    txt, md                      as is
    eml                          headers, body, attachments one level deep
    svg                          its text only
    audio and video              transcription (handled by the pipeline, not here)
    anything else                skipped, with the reason recorded
"""
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

from . import blocks as B
from . import mail, mineru, office, tabular

MINERU = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".docx", ".pptx"}
VIA_PDF = {".doc", ".ppt", ".odt", ".rtf", ".xls", ".ods"}
WORKBOOK = {".xlsx", ".xlsm"}
DELIMITED = {".csv", ".tsv"}
PLAIN = {".txt", ".md"}
AUDIO_VIDEO = {".webm", ".m4a", ".mp3", ".wav", ".ogg", ".mp4", ".mov"}
SKIPPED = {".heic": "HEIC photos aren't converted yet. Share a JPEG or PNG copy.",
           ".msg": "Outlook .msg files aren't read yet. Save the email as .eml or PDF.",
           ".vsdx": "Visio diagrams aren't read yet.",
           ".bpmn": "BPMN files aren't read yet.",
           ".xml": "XML files aren't read yet.",
           ".json": "JSON files aren't read yet."}
MAX_PLAIN = 20_000_000


@dataclass
class Converted:
    blocks: list[dict] = field(default_factory=list)
    markdown: str = ""
    converter: str = ""
    content_list: list = field(default_factory=list)  # MinerU's raw output, kept for reference
    images: dict[str, bytes] = field(default_factory=dict)
    note: str = ""  # why something was skipped or cut short; never file content
    skipped: bool = False


def _mineru(path: Path, converter: str) -> Converted:
    from ..config import get_settings
    r = mineru.convert(path)
    return Converted(blocks=r.blocks, markdown=r.markdown, content_list=r.content_list, images=r.images,
                     converter=f"{converter}:{get_settings().mineru_backend}")


def _svg_text(path: Path) -> list[dict]:
    if path.stat().st_size > 5_000_000:
        return []
    root = ElementTree.fromstring(path.read_bytes())  # expat refuses entity expansion attacks
    texts = [" ".join("".join(el.itertext()).split()) for el in root.iter() if el.tag.endswith("}text") or el.tag == "text"]
    return [{"type": "text", "text": t} for t in texts if t]


def convert(path: Path, depth: int = 0) -> Converted:
    ext = path.suffix.lower()
    if ext in MINERU:
        return _mineru(path, "mineru")
    if ext in VIA_PDF:
        with tempfile.TemporaryDirectory(prefix="gw-office-") as tmp:
            return _mineru(office.to_pdf(path, Path(tmp)), "gotenberg+mineru")
    if ext in WORKBOOK:
        blocks, note = tabular.workbook_blocks(path)
        return Converted(blocks=blocks, markdown=B.to_markdown(blocks), converter="native:workbook", note=note,
                         skipped=not blocks)
    if ext in DELIMITED:
        blocks, note = tabular.delimited_blocks(path)
        return Converted(blocks=blocks, markdown=B.to_markdown(blocks), converter="native:delimited", note=note)
    if ext in PLAIN:
        with path.open(encoding="utf-8", errors="replace") as f:
            text = f.read(MAX_PLAIN)
        blocks = B.from_markdown(text)
        return Converted(blocks=blocks, markdown=text if ext == ".md" else B.to_markdown(blocks),
                         converter="native:text")
    if ext == ".eml":
        blocks, attachments = mail.read_eml(path)
        notes = []
        if depth == 0:
            with tempfile.TemporaryDirectory(prefix="gw-mail-") as tmp:
                for name, data in attachments:
                    inner = Path(tmp) / Path(name).name
                    inner.write_bytes(data)
                    try:
                        sub = convert(inner, depth + 1)
                    except Exception as e:  # one unreadable attachment shouldn't lose the email
                        notes.append(f"Attachment {inner.name} couldn't be read ({type(e).__name__}).")
                        continue
                    if sub.blocks:
                        blocks.append({"type": "heading", "text": f"Attachment: {inner.name}", "level": 2})
                        blocks += [b | {"level": min(6, b.get("level", 1) + 2)} if b["type"] == "heading" else b
                                   for b in sub.blocks]
        return Converted(blocks=blocks, markdown=B.to_markdown(blocks), converter="native:email",
                         note=" ".join(notes))
    if ext == ".svg":
        blocks = _svg_text(path)
        return Converted(blocks=blocks, markdown=B.to_markdown(blocks), converter="native:svg",
                         skipped=not blocks, note="" if blocks else "The SVG has no text in it.")
    if ext in AUDIO_VIDEO:
        return Converted(skipped=True, note="Audio and video are transcribed instead.")
    return Converted(skipped=True, note=SKIPPED.get(ext, f"{ext or 'This'} files aren't converted yet."))
