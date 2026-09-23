from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from ..db import get_db
from ..models import Artifact, AuditEvent, Board, Job, User
from ..security import require

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview")
def overview(user: User = Depends(require("analyst")), db: DB = Depends(get_db)):
    """Coverage at a glance: who has contributed, what is waiting, what failed."""
    by_status = dict(db.execute(select(Artifact.status, func.count()).group_by(Artifact.status)).tuples().all())
    by_layer = dict(db.execute(select(Artifact.layer, func.count()).where(Artifact.status != "withdrawn")
                               .group_by(Artifact.layer)).tuples().all())
    contributors = db.scalar(select(func.count(func.distinct(Artifact.uploaded_by))))
    jobs = dict(db.execute(select(Job.status, func.count()).group_by(Job.status)).tuples().all())
    return {"artifacts_by_status": by_status, "artifacts_by_layer": by_layer,
            "contributors": contributors, "users": db.scalar(select(func.count(User.id))),
            "boards": db.scalar(select(func.count(Board.id))), "jobs": jobs}


@router.get("/audit")
def audit_log(limit: int = 200, user: User = Depends(require("admin")), db: DB = Depends(get_db)):
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.at.desc()).limit(min(limit, 1000))).all()
    return [{"at": e.at, "actor_id": e.actor_id, "actor_type": e.actor_type, "action": e.action,
             "entity": e.entity, "entity_id": e.entity_id, "detail": e.detail} for e in rows]
