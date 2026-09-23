from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from .. import audit
from ..db import get_db
from ..models import ArtifactProcess, Board, Process, User
from ..security import current_user, require
from ..util import get_or_404

router = APIRouter(prefix="/api/processes", tags=["processes"])
STATUSES = {"proposed", "confirmed", "retired"}


class ProcessIn(BaseModel):
    name: str
    description: str = ""
    parent_id: str | None = None


class ProcessPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    owner_email: EmailStr | None = None
    status: str | None = None
    parent_id: str | None = None
    clear_owner: bool = False
    clear_parent: bool = False


class MergeIn(BaseModel):
    into: str


def _same_name(db: DB, name: str, but_not: str | None = None) -> Process | None:
    q = select(Process).where(func.lower(Process.name) == name.lower(), Process.status != "retired")
    if but_not:
        q = q.where(Process.id != but_not)
    return db.scalar(q)


def find_or_propose(db: DB, name: str, user: User, request: Request) -> Process:
    """The live process with this name (any case), or a new proposed one. Staff know names we
    haven't heard yet; asking twice must not make two."""
    name = name.strip()[:200]
    existing = _same_name(db, name)
    if existing:
        return existing
    p = Process(name=name, created_by=user.id)
    db.add(p)
    db.flush()
    audit.record(db, "process.proposed", "process", p.id, actor_id=user.id, detail={"name": name}, request=request)
    return p


def _check_parent(db: DB, pid: str, parent_id: str) -> None:
    if parent_id == pid:
        raise HTTPException(422, "A process can't sit under itself.")
    node = get_or_404(db, Process, parent_id, "Parent process")
    seen = set()
    while node.parent_id and node.parent_id not in seen:
        if node.parent_id == pid:
            raise HTTPException(422, "That would put the process under one of its own sub-processes.")
        seen.add(node.parent_id)
        node = db.get(Process, node.parent_id)
        if node is None:
            break


@router.get("")
def list_processes(include_retired: bool = False, user: User = Depends(current_user), db: DB = Depends(get_db)):
    counts = dict(db.execute(select(ArtifactProcess.process_id, func.count()).group_by(ArtifactProcess.process_id)).tuples().all())
    boards = dict(db.execute(select(Board.process_id, func.count()).group_by(Board.process_id)).tuples().all())
    q = select(Process).order_by(Process.name)
    if not include_retired:
        q = q.where(Process.status != "retired")
    return [{"id": p.id, "name": p.name, "description": p.description, "parent_id": p.parent_id,
             "status": p.status, "owner_email": p.owner_email,
             "artifact_count": counts.get(p.id, 0), "board_count": boards.get(p.id, 0)} for p in db.scalars(q).all()]


@router.post("")
def create_process(body: ProcessIn, request: Request, user: User = Depends(current_user), db: DB = Depends(get_db)):
    """Anyone can propose a process. Staff know names we haven't heard yet."""
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Give the process a name.")
    existing = _same_name(db, name)
    if existing:
        return {"id": existing.id, "name": existing.name, "existing": True}
    if body.parent_id:
        get_or_404(db, Process, body.parent_id, "Parent process")
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
    changes: dict = {}
    if body.name is not None:
        name = body.name.strip()[:200]
        if not name:
            raise HTTPException(422, "Give the process a name.")
        if _same_name(db, name, but_not=pid):
            raise HTTPException(409, f"There is already a process called \"{name}\". Merge them instead.")
        changes["name"] = name
    if body.description is not None:
        changes["description"] = body.description.strip()[:4000]
    if body.status is not None:
        if body.status not in STATUSES:
            raise HTTPException(422, "Choose proposed, confirmed or retired.")
        changes["status"] = body.status
    if body.owner_email is not None:
        changes["owner_email"] = str(body.owner_email).lower()
    elif body.clear_owner:
        changes["owner_email"] = ""
    if body.parent_id is not None:
        _check_parent(db, pid, body.parent_id)
        changes["parent_id"] = body.parent_id
    elif body.clear_parent:
        changes["parent_id"] = None
    for k, v in changes.items():
        setattr(p, k, v)
    audit.record(db, "process.updated", "process", pid, actor_id=user.id, detail=changes, request=request)
    db.commit()
    return {"ok": True}


@router.post("/{pid}/merge")
def merge_process(pid: str, body: MergeIn, request: Request, user: User = Depends(require("analyst")),
                  db: DB = Depends(get_db)):
    """Fold a duplicate into the process it duplicates: its files, maps and sub-processes move
    across, and it is retired with a note saying where it went."""
    src = get_or_404(db, Process, pid, "Process")
    dst = get_or_404(db, Process, body.into, "Process to merge into")
    if src.id == dst.id:
        raise HTTPException(422, "Choose a different process to merge into.")
    if dst.status == "retired":
        raise HTTPException(422, "That process is retired. Choose one still in use.")
    _check_parent(db, src.id, dst.id)  # merging a process into its own sub-process would orphan it
    have = set(db.scalars(select(ArtifactProcess.artifact_id).where(ArtifactProcess.process_id == dst.id)).all())
    moved_files = 0
    for link in db.scalars(select(ArtifactProcess).where(ArtifactProcess.process_id == src.id)).all():
        if link.artifact_id in have:
            db.delete(link)
        else:
            db.add(ArtifactProcess(artifact_id=link.artifact_id, process_id=dst.id, step_note=link.step_note))
            db.delete(link)
            moved_files += 1
    boards = db.scalars(select(Board).where(Board.process_id == src.id)).all()
    for b in boards:
        b.process_id = dst.id
    for child in db.scalars(select(Process).where(Process.parent_id == src.id)).all():
        child.parent_id = dst.id
    src.status = "retired"
    src.description = (f"Merged into \"{dst.name}\". " + (src.description or "")).strip()[:4000]
    audit.record(db, "process.merged", "process", src.id, actor_id=user.id, request=request,
                 detail={"into": dst.id, "files": moved_files, "maps": len(boards)})
    db.commit()
    return {"ok": True, "files": moved_files, "maps": len(boards)}
