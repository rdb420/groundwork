"""Client for MinerU's `mineru-api` (FastAPI, the same service its Gradio app calls). Files go up
with POST /tasks, we poll GET /tasks/{id}, then read GET /tasks/{id}/result, which returns the
Markdown, the content_list (as a JSON string) and images as data URIs.

Long PDFs go in page windows (GW_MINERU_PAGE_BATCH) so one task never runs for hours and a
failure only repeats one window."""
import base64
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from .. import httpclient, jobs
from ..config import get_settings
from . import blocks as B


class MinerUError(RuntimeError):
    pass


@dataclass
class MinerUResult:
    markdown: str = ""
    blocks: list[dict] = field(default_factory=list)
    content_list: list = field(default_factory=list)
    images: dict[str, bytes] = field(default_factory=dict)


def _client():
    s = get_settings()
    if not s.mineru_url:
        raise MinerUError("GW_MINERU_URL is not set, so documents can't be converted.")
    return httpclient.client("mineru", base_url=s.mineru_url.rstrip("/"), timeout=120)


def _page_count(path: Path) -> int | None:
    if path.suffix.lower() != ".pdf":
        return None
    try:
        return len(PdfReader(str(path)).pages)
    except Exception:  # an unreadable PDF still goes to MinerU, which may manage; send it whole
        return None


def _task(http, path: Path, start: int | None, end: int | None) -> dict:
    s = get_settings()
    data = {"backend": s.mineru_backend, "parse_method": "auto", "lang_list": s.mineru_lang,
            "formula_enable": "true", "table_enable": "true", "return_md": "true",
            "return_content_list": "true", "return_images": "true"}
    if start is not None:
        data |= {"start_page_id": str(start), "end_page_id": str(end)}
    with path.open("rb") as f:
        r = http.post("/tasks", data=data, files={"files": (path.name, f)})
    if r.status_code != 202:
        raise MinerUError(f"MinerU refused the file ({r.status_code}).")
    task_id = r.json()["task_id"]
    deadline = time.monotonic() + s.mineru_timeout_s
    delay = 2.0
    while True:
        res = http.get(f"/tasks/{task_id}/result")
        if res.status_code == 200:
            results = res.json().get("results") or {}
            if not results:
                raise MinerUError("MinerU finished but returned nothing for the file.")
            return next(iter(results.values()))
        if res.status_code == 409:
            raise MinerUError("MinerU couldn't read the file.")
        if res.status_code not in (202, 404) or time.monotonic() > deadline:
            raise MinerUError(f"MinerU didn't finish in time ({res.status_code}).")
        jobs.heartbeat()
        time.sleep(delay)
        delay = min(delay * 1.5, 15)


def _images(raw: dict) -> dict[str, bytes]:
    out = {}
    for name, uri in (raw or {}).items():
        payload = str(uri).split(",", 1)[-1]
        try:
            out[Path(name).name] = base64.b64decode(payload)
        except ValueError:
            continue
    return out


def convert(path: Path) -> MinerUResult:
    s = get_settings()
    pages = _page_count(path)
    windows: list[tuple[int | None, int | None]] = [(None, None)]
    if pages and pages > s.mineru_page_batch:
        windows = [(i, min(i + s.mineru_page_batch, pages) - 1) for i in range(0, pages, s.mineru_page_batch)]
    out = MinerUResult()
    md_parts = []
    with _client() as http:
        for start, end in windows:
            part = _task(http, path, start, end)
            content = part.get("content_list") or "[]"
            content = json.loads(content) if isinstance(content, str) else content
            # Page numbers in a window may start at 0 again; shift them to the whole document.
            offset = start or 0
            if offset and content and max(int(b.get("page_idx", 0) or 0) for b in content) >= offset:
                offset = 0
            out.content_list += content
            out.blocks += B.from_mineru(content, offset)
            md_parts.append(part.get("md_content") or "")
            out.images |= _images(part.get("images") or {})
    out.markdown = "\n\n".join(p for p in md_parts if p.strip())
    return out
