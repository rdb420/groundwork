"""Files live on the host under data_dir. The database holds the index; a JSON sidecar
next to each file keeps it self-describing if the database is ever lost."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile

from .config import get_settings

ALLOWED_EXT = {
    ".xlsx", ".xlsm", ".xls", ".csv", ".tsv", ".ods",
    ".docx", ".doc", ".pdf", ".txt", ".md", ".rtf", ".odt",
    ".pptx", ".ppt",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".svg",
    ".msg", ".eml",
    ".webm", ".m4a", ".mp3", ".wav", ".ogg", ".mp4", ".mov",
    ".vsdx", ".bpmn", ".xml", ".json",
}


def safe_name(name: str) -> str:
    name = Path(name).name
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:180] or "file"


def artifact_dir(artifact_id: str) -> Path:
    d = datetime.now(timezone.utc)
    p = get_settings().data_dir / "artifacts" / f"{d:%Y}" / f"{d:%m}" / artifact_id
    p.mkdir(parents=True, exist_ok=True)
    return p


async def save_upload(upload: UploadFile, dest_dir: Path) -> tuple[Path, int, str]:
    """Stream to disk, enforce the size limit, return (path, size, sha256)."""
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(415, f"{ext or 'That file type'} isn't accepted yet. Ask the AI lead to add it.")
    limit = get_settings().max_upload_mb * 1024 * 1024
    path = dest_dir / ("original" + ext)
    h, size = hashlib.sha256(), 0
    with path.open("wb") as f:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                f.close()
                path.unlink(missing_ok=True)
                raise HTTPException(413, f"Files over {get_settings().max_upload_mb} MB need to be shared another way.")
            h.update(chunk)
            f.write(chunk)
    return path, size, h.hexdigest()


def write_sidecar(dest_dir: Path, meta: dict) -> None:
    (dest_dir / "metadata.json").write_text(json.dumps(meta, indent=2, default=str))
