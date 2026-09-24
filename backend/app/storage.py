"""Where files live. The database holds the index; each file is stored under a key such as
`artifacts/<id>/original.pdf`, with a JSON sidecar next to it so a folder describes itself if the
database is ever lost.

Two backends behind one interface:
- local (default): keys are paths under GW_DATA_DIR.
- s3: self-hosted Supabase Storage's S3 endpoint (or MinIO), via app/s3.py.

Code that needs a real file on disk (the malware scan, workbook reading, MinerU uploads) asks for
`local_copy(key)`; the local backend hands back the file itself, the S3 backend a temporary copy.
"""
import hashlib
import json
import mimetypes
import re
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse

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
KEY = re.compile(r"^(artifacts|recordings)/[A-Za-z0-9._/ -]+$")


def safe_name(name: str) -> str:
    name = Path(name).name
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:180] or "file"


def check_key(key: str) -> str:
    """Keys come from our own code, but a bad one must never reach outside the store."""
    if not KEY.match(key) or ".." in key.split("/"):
        raise ValueError(f"not a storage key: {key[:80]!r}")
    return key


class Storage(Protocol):
    def put_file(self, key: str, path: Path, content_type: str = ..., sha256: str | None = ...) -> None: ...
    def put_bytes(self, key: str, data: bytes, content_type: str = ...) -> None: ...
    def read_bytes(self, key: str, limit: int | None = None) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete_prefix(self, prefix: str) -> int: ...
    def local_copy(self, key: str): ...  # context manager yielding a Path
    def response(self, key: str, media_type: str, filename: str, disposition: str,
                 headers: dict[str, str]) -> Response: ...


def content_disposition(disposition: str, filename: str) -> str:
    quoted = quote(filename)
    if quoted != filename:
        return f"{disposition}; filename*=utf-8''{quoted}"
    return f'{disposition}; filename="{filename}"'


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root

    def path(self, key: str) -> Path:
        return self.root / check_key(key)

    def put_file(self, key: str, path: Path, content_type: str = "application/octet-stream",
                 sha256: str | None = None) -> None:
        dest = self.path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if path.resolve() != dest.resolve():
            shutil.copyfile(path, dest)

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        dest = self.path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    def read_bytes(self, key: str, limit: int | None = None) -> bytes:
        with self.path(key).open("rb") as f:
            return f.read(limit if limit is not None else -1)

    def exists(self, key: str) -> bool:
        return self.path(key).is_file()

    def delete_prefix(self, prefix: str) -> int:
        target = self.path(prefix.rstrip("/"))
        if target.is_dir():
            n = sum(1 for p in target.rglob("*") if p.is_file())
            shutil.rmtree(target, ignore_errors=True)
            return n
        if target.is_file():
            target.unlink()
            return 1
        return 0

    @contextmanager
    def local_copy(self, key: str) -> Iterator[Path]:
        yield self.path(key)

    def response(self, key: str, media_type: str, filename: str, disposition: str,
                 headers: dict[str, str]) -> Response:
        return FileResponse(self.path(key), media_type=media_type, filename=filename,
                            content_disposition_type=disposition, headers=headers)


class S3Storage:
    def __init__(self):
        from .s3 import S3
        s = get_settings()
        self.s3 = S3(s.s3_endpoint, s.s3_bucket, s.s3_access_key, s.s3_secret_key, s.s3_region, s.s3_ca_file)

    def put_file(self, key: str, path: Path, content_type: str = "application/octet-stream",
                 sha256: str | None = None) -> None:
        self.s3.put_file(check_key(key), path, content_type, sha256)

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.s3.put_bytes(check_key(key), data, content_type)

    def read_bytes(self, key: str, limit: int | None = None) -> bytes:
        out = bytearray()
        for chunk in self.s3.stream(check_key(key)):
            out += chunk
            if limit is not None and len(out) >= limit:
                return bytes(out[:limit])
        return bytes(out)

    def exists(self, key: str) -> bool:
        return self.s3.exists(check_key(key))

    def delete_prefix(self, prefix: str) -> int:
        keys = self.s3.list(check_key(prefix))
        for k in keys:
            self.s3.delete(k)
        return len(keys)

    @contextmanager
    def local_copy(self, key: str) -> Iterator[Path]:
        with tempfile.TemporaryDirectory(prefix="gw-") as tmp:
            path = Path(tmp) / Path(key).name
            with path.open("wb") as f:
                for chunk in self.s3.stream(check_key(key)):
                    f.write(chunk)
            yield path

    def response(self, key: str, media_type: str, filename: str, disposition: str,
                 headers: dict[str, str]) -> Response:
        return StreamingResponse(self.s3.stream(check_key(key)), media_type=media_type,
                                 headers={**headers, "Content-Disposition": content_disposition(disposition, filename)})


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    if s.storage_backend == "s3":
        return S3Storage()
    if s.storage_backend != "local":
        raise RuntimeError("GW_STORAGE_BACKEND must be local or s3.")
    return LocalStorage(s.data_dir)


def artifact_prefix(artifact_id: str) -> str:
    return f"artifacts/{artifact_id}/"


def prefix_of(key: str) -> str:
    """The folder a stored file sits in, for purging. Older files sit under artifacts/YYYY/MM/<id>/."""
    return check_key(key).rsplit("/", 1)[0] + "/"


def guess_type(key: str) -> str:
    return mimetypes.guess_type(key)[0] or "application/octet-stream"


async def save_upload(upload: UploadFile, key: str) -> tuple[int, str]:
    """Stream to a temporary file under the size limit, hash it, then hand it to storage.
    Returns (size, sha256)."""
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(415, f"{ext or 'That file type'} isn't accepted yet. Ask the AI lead to add it.")
    limit = get_settings().max_upload_mb * 1024 * 1024
    h, size = hashlib.sha256(), 0
    with tempfile.TemporaryDirectory(prefix="gw-up-") as tmp:
        path = Path(tmp) / ("original" + ext)
        with path.open("wb") as f:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"Files over {get_settings().max_upload_mb} MB need to be shared another way.")
                h.update(chunk)
                f.write(chunk)
        get_storage().put_file(key, path, guess_type(key), h.hexdigest())
    return size, h.hexdigest()


def write_sidecar(prefix: str, meta: dict) -> None:
    get_storage().put_bytes(prefix + "metadata.json", json.dumps(meta, indent=2, default=str).encode(),
                            "application/json")
