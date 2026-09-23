from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from .. import audit, retention
from ..config import get_settings
from ..db import get_db
from ..models import AIDraft, Artifact, ArtifactProcess, AuditEvent, Board, Job, Process, Recording, User
from ..security import require
from ..util import get_or_404

router = APIRouter(prefix="/api/admin", tags=["admin"])

LAYERS = ("declared", "system", "actual", "workaround", "unsure")
IN_USE = ("withdrawn", "purged", "quarantined")  # statuses that no longer count as evidence


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


def _flags(layers: dict[str, int], maps: int) -> list[str]:
    total = sum(layers.values())
    out = []
    if not total:
        out.append("No files yet")
    elif layers["declared"] and not (layers["actual"] or layers["workaround"]):
        out.append("Only the official version so far")
    elif (layers["actual"] or layers["workaround"]) and not layers["declared"]:
        out.append("No official version shared")
    if layers["workaround"]:
        out.append(f"{layers['workaround']} workaround{'s' if layers['workaround'] > 1 else ''}")
    if not maps:
        out.append("Not mapped yet")
    return out


@router.get("/coverage")
def coverage(user: User = Depends(require("analyst")), db: DB = Depends(get_db)):
    """The coverage view from the rollout plan: evidence per process by layer, who contributed,
    map status, and the measures in ARCHITECTURE.md section 7."""
    evidence = (Artifact.status.not_in(IN_USE), Artifact.board_id.is_(None))
    layer_rows = db.execute(select(ArtifactProcess.process_id, Artifact.layer, func.count())
                            .join(Artifact, Artifact.id == ArtifactProcess.artifact_id).where(*evidence)
                            .group_by(ArtifactProcess.process_id, Artifact.layer)).tuples().all()
    people_rows = db.execute(select(ArtifactProcess.process_id, func.count(func.distinct(Artifact.uploaded_by)))
                             .join(Artifact, Artifact.id == ArtifactProcess.artifact_id).where(*evidence)
                             .group_by(ArtifactProcess.process_id)).tuples().all()
    boards = db.scalars(select(Board).where(Board.process_id.is_not(None))).all()
    drafts = db.execute(select(Board.process_id, AIDraft.status, func.count()).join(Board, Board.id == AIDraft.board_id)
                        .where(AIDraft.mode != "combine").group_by(Board.process_id, AIDraft.status)).tuples().all()

    layers: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(LAYERS, 0))
    for pid, layer, n in layer_rows:
        layers[pid][layer if layer in LAYERS else "unsure"] += n
    people = dict(people_rows)
    maps: dict[str, dict] = defaultdict(lambda: {"overview": 0, "views": 0, "other": 0, "to_confirm": 0})
    for b in boards:
        m = maps[b.process_id or ""]
        m["overview" if b.session_pass == "overview" and not b.perspective else "views" if b.perspective else "other"] += 1
        m["to_confirm"] += (b.document_markdown or "").count("[TO CONFIRM")
    decided: dict[str, dict[str, int]] = defaultdict(lambda: {"accepted": 0, "discarded": 0, "draft": 0})
    for board_pid, status, n in drafts:
        decided[board_pid or ""][status] = decided[board_pid or ""].get(status, 0) + n

    rows: list[dict[str, Any]] = []
    for p in db.scalars(select(Process).where(Process.status != "retired").order_by(Process.name)).all():
        m = maps[p.id]
        map_count = m["overview"] + m["views"] + m["other"]
        rows.append({"id": p.id, "name": p.name, "parent_id": p.parent_id, "status": p.status,
                     "owner_email": p.owner_email, "layers": layers[p.id], "files": sum(layers[p.id].values()),
                     "contributors": people.get(p.id, 0), "maps": m | {"total": map_count},
                     "drafts": decided[p.id], "flags": _flags(layers[p.id], map_count)})

    who = db.execute(select(User.display_name, User.email, User.team, func.count(Artifact.id))
                     .join(Artifact, Artifact.uploaded_by == User.id).where(*evidence)
                     .group_by(User.id).order_by(func.count(Artifact.id).desc())).tuples().all()
    files = db.scalar(select(func.count()).select_from(Artifact).where(*evidence)) or 0
    workaround = db.scalar(select(func.count()).select_from(Artifact).where(*evidence, Artifact.layer == "workaround")) or 0
    leaves = [r for r in rows if not any(c["parent_id"] == r["id"] for c in rows)]
    all_drafts = {k: sum(d[k] for d in decided.values()) for k in ("accepted", "discarded", "draft")}
    return {
        "processes": rows,
        "contributors": [{"name": n or e, "email": e, "team": t, "files": c} for n, e, t, c in who],
        "totals": {"files": files, "workaround_share": round(workaround / files, 2) if files else 0,
                   "processes": len(leaves), "processes_with_files": sum(1 for r in leaves if r["files"]),
                   "processes_with_map": sum(1 for r in leaves if r["maps"]["total"]),
                   "drafts": all_drafts, "to_confirm": sum(m["to_confirm"] for m in maps.values())},
    }


@router.get("/audit")
def audit_log(limit: int = 200, user: User = Depends(require("admin")), db: DB = Depends(get_db)):
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.at.desc()).limit(min(limit, 1000))).all()
    return [{"at": e.at, "actor_id": e.actor_id, "actor_type": e.actor_type, "action": e.action,
             "entity": e.entity, "entity_id": e.entity_id, "detail": e.detail} for e in rows]


# ---- Retention and purge ----------------------------------------------------------------

@router.get("/retention")
def retention_status(user: User = Depends(require("admin")), db: DB = Depends(get_db)):
    s = get_settings()
    d = retention.due(db)
    return {"withdrawn_days": s.retention_withdrawn_days, "audio_days": s.retention_audio_days,
            "auto": s.retention_auto, "backup_keep_days": s.backup_keep_days,
            "files": [{"id": a.id, "title": a.title, "withdrawn_at": a.withdrawn_at} for a in d["files"]],
            "audio": [{"id": r.id, "board_id": r.board_id, "ended_at": r.ended_at} for r in d["audio"]]}


@router.post("/retention/run")
def retention_run(request: Request, user: User = Depends(require("admin")), db: DB = Depends(get_db)):
    done = retention.run(db, actor_id=user.id)
    audit.record(db, "retention.run", "system", actor_id=user.id, request=request, detail=done)
    db.commit()
    return done


class PurgeIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.post("/artifacts/{aid}/purge")
def purge_artifact(aid: str, body: PurgeIn, request: Request, user: User = Depends(require("admin")),
                   db: DB = Depends(get_db)):
    """Delete one file now, for example personal information shared by mistake."""
    a = get_or_404(db, Artifact, aid, "File")
    if a.status == "purged":
        raise HTTPException(409, "This file has already been deleted.")
    retention.purge_artifact(db, a, actor_id=user.id, reason=body.reason.strip())
    audit.record(db, "artifact.purge_requested", "artifact", aid, actor_id=user.id, request=request,
                 detail={"reason": body.reason.strip()})
    db.commit()
    return {"ok": True}


@router.post("/recordings/{rid}/purge-audio")
def purge_recording_audio(rid: str, body: PurgeIn, request: Request, user: User = Depends(require("admin")),
                          db: DB = Depends(get_db)):
    r = get_or_404(db, Recording, rid, "Recording")
    retention.purge_audio(db, r, actor_id=user.id, reason=body.reason.strip())
    audit.record(db, "recording.purge_requested", "recording", rid, actor_id=user.id, request=request,
                 detail={"reason": body.reason.strip()})
    db.commit()
    return {"ok": True}
