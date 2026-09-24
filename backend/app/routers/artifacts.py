"""Evidence intake. A contributor uploads one or more files with a short description of
what each is and which process it belongs to. Files wait on the host for processing."""
import json
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session as DB
from sqlalchemy.orm import selectinload

from .. import access, audit, scan
from ..db import get_db
from ..models import Artifact, ArtifactProcess, Board, Job, Process, User, uid
from ..security import can_see_all, current_user, utcnow
from ..storage import artifact_prefix, get_storage, safe_name, save_upload, write_sidecar
from ..util import get_or_404
from .processes import find_or_propose

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])

INLINE_IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
CANVAS_IMAGES = INLINE_IMAGES | {".svg"}
KINDS = {"spreadsheet", "procedure", "form", "report", "email", "photo", "diagram", "other"}
LAYERS = {"declared", "system", "actual", "workaround", "unsure"}
FREQ = {"", "daily", "weekly", "monthly", "quarterly", "yearly", "adhoc"}


class ArtifactMeta(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    kind: str = "other"
    layer: str = "unsure"
    frequency: str = ""
    source_system: str = ""
    maintained_by: str = ""
    personal_info: str = "unsure"
    is_current: bool = True
    if_it_disappeared: str = ""
    process_ids: list[str] = []
    new_process_names: list[str] = []
    step_note: str = ""
    board_id: str | None = None

    def check(self):
        if self.kind not in KINDS or self.layer not in LAYERS or self.frequency not in FREQ \
                or self.personal_info not in {"yes", "no", "unsure"}:
            raise HTTPException(422, "One of the choices wasn't recognised. Reload the form and try again.")


def to_dict(a: Artifact) -> dict:
    return {
        "id": a.id, "title": a.title, "description": a.description, "kind": a.kind, "layer": a.layer,
        "frequency": a.frequency, "source_system": a.source_system, "maintained_by": a.maintained_by,
        "personal_info": a.personal_info, "is_current": a.is_current, "if_it_disappeared": a.if_it_disappeared,
        "original_filename": a.original_filename, "mime_type": a.mime_type, "size_bytes": a.size_bytes,
        "status": a.status, "uploaded_at": a.uploaded_at, "uploaded_by": a.uploader.email if a.uploader else None,
        "processes": [{"id": p.id, "name": p.name} for p in a.processes], "profile": a.profile,
        "board_id": a.board_id, "scan": a.scan,
    }


@router.post("")
async def upload(request: Request, file: UploadFile = File(...), meta: str = Form(...),
                 user: User = Depends(current_user), db: DB = Depends(get_db)):
    try:
        m = ArtifactMeta.model_validate(json.loads(meta))
    except (ValidationError, json.JSONDecodeError):
        raise HTTPException(422, "Add a title so others can find this file.") from None
    m.check()
    if m.board_id:
        # Canvas images are visible to everyone who can open the map, so only images go there.
        access.open_board(db, m.board_id, user)
        if Path(file.filename or "").suffix.lower() not in CANVAS_IMAGES:
            raise HTTPException(415, "Only PNG, JPEG, GIF, WebP or SVG images can go on a map. Share other files from Share files.")
    for pid in m.process_ids:
        get_or_404(db, Process, pid, "Process")

    a = Artifact(id=uid(), uploaded_by=user.id, original_filename=safe_name(file.filename or "file"), stored_path="",
                 sha256="", title=m.title.strip(), description=m.description, kind=m.kind, layer=m.layer,
                 frequency=m.frequency, source_system=m.source_system, maintained_by=m.maintained_by,
                 personal_info=m.personal_info, is_current=m.is_current, if_it_disappeared=m.if_it_disappeared,
                 board_id=m.board_id)
    prefix = artifact_prefix(a.id)
    key = prefix + "original" + Path(a.original_filename).suffix.lower()
    size, sha = await save_upload(file, key)
    a.storage_key, a.size_bytes, a.sha256 = key, size, sha
    # The server decides the type from the extension it allowed; the browser's claim is ignored.
    a.mime_type = mimetypes.guess_type(a.original_filename)[0] or "application/octet-stream"

    duplicate = db.scalar(select(Artifact).where(Artifact.sha256 == sha, Artifact.status != "withdrawn"))
    db.add(a)
    db.flush()

    pids = set(m.process_ids)
    for name in m.new_process_names:
        if name.strip():
            pids.add(find_or_propose(db, name, user, request).id)
    for pid in pids:
        db.add(ArtifactProcess(artifact_id=a.id, process_id=pid, step_note=m.step_note))

    db.add(Job(kind="profile_artifact", ref_id=a.id))
    audit.record(db, "artifact.uploaded", "artifact", a.id, actor_id=user.id, request=request,
                 detail={"filename": a.original_filename, "size": size, "sha256": sha,
                         "duplicate_of": duplicate.id if duplicate else None})
    db.commit()
    write_sidecar(prefix, {**m.model_dump(), "artifact_id": a.id, "uploaded_by": user.email,
                      "uploaded_at": a.uploaded_at, "original_filename": a.original_filename,
                      "sha256": sha, "size_bytes": size, "process_ids": sorted(pids)})
    db.refresh(a)
    return {**to_dict(a), "duplicate_of": duplicate.id if duplicate else None}


@router.get("")
def list_artifacts(mine: bool = False, process_id: str | None = None, user: User = Depends(current_user),
                   db: DB = Depends(get_db)):
    q = (select(Artifact).options(selectinload(Artifact.processes), selectinload(Artifact.uploader))
         .where(Artifact.status.not_in(("withdrawn", "purged")), Artifact.board_id.is_(None)).order_by(Artifact.uploaded_at.desc()))
    if mine or not can_see_all(user):
        q = q.where(Artifact.uploaded_by == user.id)
    if process_id:
        q = q.join(ArtifactProcess).where(ArtifactProcess.process_id == process_id)
    return [to_dict(a) for a in db.scalars(q).all()]


def _visible(db: DB, a: Artifact, user: User):
    """Your own files, everything for analysts, and images on maps you can open."""
    if a.uploaded_by == user.id or can_see_all(user):
        return
    if a.board_id:
        board = db.get(Board, a.board_id)
        if board and access.can_open_board(board, user):
            return
    raise HTTPException(404, "File not found.")


@router.get("/{aid}")
def get_artifact(aid: str, user: User = Depends(current_user), db: DB = Depends(get_db)):
    a = get_or_404(db, Artifact, aid, "File")
    _visible(db, a, user)
    return to_dict(a)


@router.get("/{aid}/file")
def download(aid: str, request: Request, user: User = Depends(current_user), db: DB = Depends(get_db)):
    a = get_or_404(db, Artifact, aid, "File")
    _visible(db, a, user)
    if a.status == "purged":
        raise HTTPException(410, "This file was deleted under the retention rules. Ask the person who shared it.")
    if a.scan == "infected" or a.status == "quarantined":
        raise HTTPException(403, "The malware check flagged this file, so it can't be downloaded. Ask an admin.")
    if scan.enabled() and a.scan == "":
        raise HTTPException(409, "This file is still being checked for malware. Try again in a minute.")
    audit.record(db, "artifact.downloaded", "artifact", a.id, actor_id=user.id, request=request)
    db.commit()
    # Only raster images display in the browser. Everything else, SVG included, downloads, and the
    # sandbox policy stops any script in a file from running in the portal's origin.
    ext = Path(a.storage_key).suffix.lower()
    mime = mimetypes.guess_type(f"x{ext}")[0] or "application/octet-stream"
    return get_storage().response(a.storage_key, mime, a.original_filename,
                                  "inline" if ext in INLINE_IMAGES else "attachment",
                                  {"Content-Security-Policy": "default-src 'none'; img-src 'self'; sandbox",
                                   "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


@router.post("/{aid}/withdraw")
def withdraw(aid: str, request: Request, user: User = Depends(current_user), db: DB = Depends(get_db)):
    """Contributors can take back what they shared. The file stays on disk for the audit trail
    until an admin purges it under the retention rule."""
    a = get_or_404(db, Artifact, aid, "File")
    if a.uploaded_by != user.id and user.role != "admin":
        raise HTTPException(403, "Only the person who uploaded this can withdraw it.")
    if a.status == "purged":
        raise HTTPException(409, "This file has already been deleted.")
    a.status, a.withdrawn_at = "withdrawn", utcnow()
    audit.record(db, "artifact.withdrawn", "artifact", a.id, actor_id=user.id, request=request)
    db.commit()
    return {"ok": True}
