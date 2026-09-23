from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from .. import audit
from ..db import get_db
from ..models import ArtifactProcess, Board, Process, User
from ..security import current_user, require
from ..util import get_or_404

router = APIRouter(prefix="/api/processes", tags=["processes"])


class ProcessIn(BaseModel):
    name: str
    description: str = ""
    parent_id: str | None = None


class ProcessPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    owner_email: str | None = None
    status: str | None = None
    parent_id: str | None = None


@router.get("")
def list_processes(user: User = Depends(current_user), db: DB = Depends(get_db)):
    counts = dict(db.execute(select(ArtifactProcess.process_id, func.count()).group_by(ArtifactProcess.process_id)).tuples().all())
    boards = dict(db.execute(select(Board.process_id, func.count()).group_by(Board.process_id)).tuples().all())
    rows = db.scalars(select(Process).where(Process.status != "retired").order_by(Process.name)).all()
    return [{"id": p.id, "name": p.name, "description": p.description, "parent_id": p.parent_id,
             "status": p.status, "owner_email": p.owner_email,
             "artifact_count": counts.get(p.id, 0), "board_count": boards.get(p.id, 0)} for p in rows]


@router.post("")
def create_process(body: ProcessIn, request: Request, user: User = Depends(current_user), db: DB = Depends(get_db)):
    """Anyone can propose a process. Staff know names we haven't heard yet."""
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Give the process a name.")
    existing = db.scalar(select(Process).where(func.lower(Process.name) == name.lower()))
    if existing:
        return {"id": existing.id, "name": existing.name, "existing": True}
    p = Process(name=name[:200], description=body.description, parent_id=body.parent_id, created_by=user.id)
    db.add(p)
    db.flush()
    audit.record(db, "process.proposed", "process", p.id, actor_id=user.id, detail={"name": name}, request=request)
    db.commit()
    return {"id": p.id, "name": p.name, "existing": False}


@router.patch("/{pid}")
def patch_process(pid: str, body: ProcessPatch, request: Request, user: User = Depends(require("analyst")),
                  db: DB = Depends(get_db)):
    p = get_or_404(db, Process, pid, "Process")
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(p, k, v)
    audit.record(db, "process.updated", "process", pid, actor_id=user.id, detail=changes, request=request)
    db.commit()
    return {"ok": True}
