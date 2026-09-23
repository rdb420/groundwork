"""Plain-text extraction for search and AI context. Stores a preview, not the full text,
in the profile; the full text is written next to the original."""
import re
import zipfile
from pathlib import Path

from pypdf import PdfReader

PREVIEW = 1500


def extract_text(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in {".txt", ".md", ".csv", ".tsv"}:
        return path.read_text(errors="replace")
    if ext == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join((p.extract_text() or "") for p in reader.pages[:200])
    if ext == ".docx":
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf8", "replace")
        xml = re.sub(r"</w:p>", "\n", xml)
        return re.sub(r"<[^>]+>", "", xml)
    return None


def profile_document(path: Path) -> dict | None:
    text = extract_text(path)
    if text is None:
        return None
    (path.parent / "extracted.txt").write_text(text)
    words = len(text.split())
    pages = None
    if path.suffix.lower() == ".pdf":
        pages = len(PdfReader(str(path)).pages)
    summary = f"Document of about {words} words" + (f" over {pages} pages" if pages else "") + "."
    if words < 20 and path.suffix.lower() == ".pdf":
        summary += " Little text found; it may be a scan that needs OCR."
    return {"type": "document", "summary": summary, "words": words, "pages": pages, "preview": text[:PREVIEW]}
