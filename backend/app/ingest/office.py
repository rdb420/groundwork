"""Older and open Office formats (doc, ppt, odt, rtf, xls, ods) become PDF in a Gotenberg container
(LibreOffice behind an HTTP API), then go to MinerU like any PDF. Untrusted Office files are
opened there, never inside Groundwork's own containers."""
from pathlib import Path

from .. import httpclient
from ..config import get_settings


class OfficeError(RuntimeError):
    pass


def to_pdf(path: Path, out_dir: Path) -> Path:
    s = get_settings()
    if not s.gotenberg_url:
        raise OfficeError("GW_GOTENBERG_URL is not set, so this Office format can't be converted.")
    with httpclient.client("gotenberg", base_url=s.gotenberg_url.rstrip("/"), timeout=300) as http, path.open("rb") as f:
        r = http.post("/forms/libreoffice/convert", files={"files": (path.name, f)})
    if r.status_code != 200 or not r.content.startswith(b"%PDF"):
        raise OfficeError(f"The Office converter couldn't read the file ({r.status_code}).")
    pdf = out_dir / (path.stem + ".pdf")
    pdf.write_bytes(r.content)
    return pdf
