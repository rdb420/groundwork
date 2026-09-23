"""Evidence intake. A contributor uploads one or more files with a short description of
what each is and which process it belongs to. Files wait on the host for processing."""
import json
import mimetypes
import shutil

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session as DB
from sqlalchemy.orm import selectinload

from .. import audit, scan
from ..db import get_db
from ..models import Artifact, ArtifactProcess, Job, Process, User, uid
from ..security import can_see_all, current_user, utcnow
from ..storage import artifact_dir, safe_name, save_upload, write_sidecar
from ..util import get_or_404
from .processes import find_or_propose

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])

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

    a = Artifact(id=uid(), uploaded_by=user.id, original_filename=safe_name(file.filename or "file"), stored_path="",
                 sha256="", title=m.title.strip(), description=m.description, kind=m.kind, layer=m.layer,
                 frequency=m.frequency, source_system=m.source_system, maintained_by=m.maintained_by,
                 personal_info=m.personal_info, is_current=m.is_current, if_it_disappeared=m.if_it_disappeared,
                 board_id=m.board_id)
    d = artifact_dir(a.id)
    try:
        path, size, sha = await save_upload(file, d)
    except HTTPException:
        shutil.rmtree(d, ignore_errors=True)
        raise
    a.stored_path, a.size_bytes, a.sha256 = str(path), size, sha
    a.mime_type = file.content_type or mimetypes.guess_type(a.original_filename)[0] or ""

    duplicate = db.scalar(select(Artifact).where(Artifact.sha256 == sha, Artifact.status != "withdrawn"))
    db.add(a)
    db.flush()

    pids = set(m.process_ids)
    for name in m.new_process_names:
        if name.strip():
            pids.add(find_or_propose(db, name, user, request).id)
    for pid in pids:
        if db.get(Process, pid):
            db.add(ArtifactProcess(artifact_id=a.id, process_id=pid, step_note=m.step_note))

    db.add(Job(kind="profile_artifact", ref_id=a.id))
    audit.record(db, "artifact.uploaded", "artifact", a.id, actor_id=user.id, request=request,
                 detail={"filename": a.original_filename, "size": size, "sha256": sha,
                         "duplicate_of": duplicate.id if duplicate else None})
    db.commit()
    write_sidecar(d, {**m.model_dump(), "artifact_id": a.id, "uploaded_by": user.email,
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


def _visible(a: Artifact, user: User):
    if a.uploaded_by != user.id and not can_see_all(user) and not a.board_id:
        raise HTTPException(404, "File not found.")


@router.get("/{aid}")
def get_artifact(aid: str, user: User = Depends(current_user), db: DB = Depends(get_db)):
    a = get_or_404(db, Artifact, aid, "File")
    _visible(a, user)
    return to_dict(a)


@router.get("/{aid}/file")
def download(aid: str, request: Request, user: User = Depends(current_user), db: DB = Depends(get_db)):
    a = get_or_404(db, Artifact, aid, "File")
    _visible(a, user)
    if a.status == "purged":
        raise HTTPException(410, "This file was deleted under the retention rules. Ask the person who shared it.")
    if a.scan == "infected" or a.status == "quarantined":
        raise HTTPException(403, "The malware check flagged this file, so it can't be downloaded. Ask an admin.")
    if scan.enabled() and a.scan == "":
        raise HTTPException(409, "This file is still being checked for malware. Try again in a minute.")
    audit.record(db, "artifact.downloaded", "artifact", a.id, actor_id=user.id, request=request)
    db.commit()
    inline = a.mime_type.startswith("image/")
    return FileResponse(a.stored_path, media_type=a.mime_type or None, filename=a.original_filename,
                        content_disposition_type="inline" if inline else "attachment")


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
