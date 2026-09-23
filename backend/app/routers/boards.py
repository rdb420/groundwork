"""Process-mapping boards, session recordings and AI drafts."""
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from .. import audit
from ..ai.generate import GenerationRefused, generate_for_board
from ..config import get_settings
from ..db import get_db
from ..models import AIDraft, Board, Job, Recording, TranscriptSegment, User
from ..security import can_see_all, current_user, utcnow
from ..storage import ALLOWED_EXT
from ..util import get_or_404

router = APIRouter(prefix="/api", tags=["boards"])


class BoardIn(BaseModel):
    title: str
    process_id: str | None = None
    personal_info: bool = False
    perspective: str = ""  # whose view, for one-person maps in the detail pass
    session_pass: str = "overview"


class BoardSave(BaseModel):
    version: int
    doc: dict
    title: str | None = None
    process_id: str | None = None
    personal_info: bool | None = None


class RecordingIn(BaseModel):
    consent_note: str


class GenerateIn(BaseModel):
    mode: str = "sop"  # sop | workflow | questions
    guidance: str = ""


def board_dict(b: Board, with_doc: bool = False) -> dict:
    d: dict[str, Any] = {"id": b.id, "title": b.title, "process_id": b.process_id,
         "process_name": b.process.name if b.process else None, "version": b.version,
         "updated_at": b.updated_at, "created_at": b.created_at, "personal_info": b.personal_info,
         "node_count": len(b.doc.get("nodes", [])), "session_pass": b.session_pass or "detail",
         "perspective": b.perspective or ""}
    if with_doc:
        d["doc"] = b.doc
        d["rules"] = b.rules or []
    return d


def _board(db: DB, bid: str, user: User) -> Board:
    """Boards are shared workspaces: any signed-in person can open one they have the link to.
    Tighten here if a board ever holds material only some staff should see."""
    return get_or_404(db, Board, bid, "Board")


@router.get("/boards")
def list_boards(user: User = Depends(current_user), db: DB = Depends(get_db)):
    q = select(Board).order_by(Board.updated_at.desc())
    if not can_see_all(user):
        q = q.where(Board.created_by == user.id)
    return [board_dict(b) for b in db.scalars(q).all()]


@router.post("/boards")
def create_board(body: BoardIn, request: Request, user: User = Depends(current_user), db: DB = Depends(get_db)):
    if body.session_pass not in {"overview", "detail"}:
        raise HTTPException(422, "Choose the overview or the detail pass.")
    b = Board(title=body.title.strip()[:300] or "Untitled map", process_id=body.process_id,
              created_by=user.id, personal_info=body.personal_info, perspective=body.perspective.strip()[:200],
              session_pass="detail" if body.perspective.strip() else body.session_pass)
    db.add(b)
    db.flush()
    audit.record(db, "board.created", "board", b.id, actor_id=user.id, request=request)
    db.commit()
    return board_dict(b, with_doc=True)


@router.get("/boards/{bid}")
def get_board(bid: str, user: User = Depends(current_user), db: DB = Depends(get_db)):
    return board_dict(_board(db, bid, user), with_doc=True)


@router.put("/boards/{bid}")
def save_board(bid: str, body: BoardSave, request: Request, user: User = Depends(current_user),
               db: DB = Depends(get_db)):
    """Optimistic concurrency: the client sends the version it loaded. A mismatch means
    someone else saved first; the client reloads rather than overwriting their work."""
    b = _board(db, bid, user)
    if body.version != b.version:
        raise HTTPException(409, "Someone else changed this map. Reload to see their changes.")
    if not isinstance(body.doc.get("nodes"), list) or not isinstance(body.doc.get("edges"), list):
        raise HTTPException(422, "The map data was incomplete, so it wasn't saved.")
    b.doc = body.doc
    for field in ("title", "process_id", "personal_info"):
        v = getattr(body, field)
        if v is not None:
            setattr(b, field, v)
    b.version += 1
    b.updated_at = utcnow()
    # Autosave fires often; audit the fact of an edit, not every keystroke.
    audit.record(db, "board.saved", "board", b.id, actor_id=user.id, request=request,
                 detail={"version": b.version, "nodes": len(b.doc["nodes"]), "edges": len(b.doc["edges"])})
    db.commit()
    return {"version": b.version, "updated_at": b.updated_at}


# ---- Recording and transcription -------------------------------------------------------

@router.post("/boards/{bid}/recordings")
def start_recording(bid: str, body: RecordingIn, request: Request, user: User = Depends(current_user),
                    db: DB = Depends(get_db)):
    _board(db, bid, user)
    if len(body.consent_note.strip()) < 3:
        raise HTTPException(422, "Record who agreed to be recorded before you start.")
    r = Recording(board_id=bid, started_by=user.id, consent_note=body.consent_note.strip())
    db.add(r)
    db.flush()
    audit.record(db, "recording.started", "recording", r.id, actor_id=user.id, request=request,
                 detail={"board_id": bid, "consent": r.consent_note})
    db.commit()
    return {"id": r.id}


@router.post("/recordings/{rid}/chunks")
async def upload_chunk(rid: str, seq: int, request: Request, file: UploadFile = File(...),
                       user: User = Depends(current_user), db: DB = Depends(get_db)):
    r = get_or_404(db, Recording, rid, "Recording")
    if r.status != "recording":
        raise HTTPException(409, "This recording has ended.")
    ext = "." + (file.filename or "chunk.webm").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        ext = ".webm"
    d = get_settings().data_dir / "recordings" / rid
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{seq:05d}{ext}"
    path.write_bytes(await file.read())
    seg = TranscriptSegment(recording_id=rid, seq=seq, audio_path=str(path))
    db.add(seg)
    db.flush()
    if get_settings().transcription_provider == "none":
        seg.status = "skipped"
    else:
        db.add(Job(kind="transcribe_segment", ref_id=seg.id))
    audit.record(db, "recording.chunk_received", "recording", rid, actor_id=user.id, request=request,
                 detail={"seq": seq, "segment_id": seg.id})
    db.commit()
    return {"segment_id": seg.id, "status": seg.status}


@router.post("/recordings/{rid}/end")
def end_recording(rid: str, request: Request, user: User = Depends(current_user), db: DB = Depends(get_db)):
    r = get_or_404(db, Recording, rid, "Recording")
    r.status, r.ended_at = "ended", utcnow()
    audit.record(db, "recording.ended", "recording", rid, actor_id=user.id, request=request)
    db.commit()
    return {"ok": True}


@router.get("/boards/{bid}/transcript")
def transcript(bid: str, user: User = Depends(current_user), db: DB = Depends(get_db)):
    _board(db, bid, user)
    rows = db.execute(
        select(Recording, TranscriptSegment).join(TranscriptSegment, TranscriptSegment.recording_id == Recording.id)
        .where(Recording.board_id == bid).order_by(Recording.started_at, TranscriptSegment.seq)).all()
    return [{"recording_id": r.id, "seq": s.seq, "status": s.status, "text": s.text, "at": s.created_at}
            for r, s in rows]


# ---- AI drafts --------------------------------------------------------------------------

@router.post("/boards/{bid}/generate")
def generate(bid: str, body: GenerateIn, request: Request, user: User = Depends(current_user),
             db: DB = Depends(get_db)):
    b = _board(db, bid, user)
    if body.mode not in {"sop", "workflow", "questions"}:
        raise HTTPException(422, "Choose an SOP draft, a workflow draft or interview questions.")
    try:
        draft = generate_for_board(db, b, user, body.mode, body.guidance)
    except GenerationRefused as e:
        raise HTTPException(409, str(e)) from e
    audit.record(db, "ai.draft_created", "ai_draft", draft.id, actor_id=user.id, actor_type="ai", request=request,
                 detail={"board_id": bid, "mode": body.mode, "provider": draft.provider, "model": draft.model,
                         "board_version": draft.board_version})
    db.commit()
    return draft_dict(draft)


def draft_dict(d: AIDraft) -> dict:
    return {"id": d.id, "mode": d.mode, "provider": d.provider, "model": d.model, "created_at": d.created_at,
            "board_version": d.board_version, "markdown": d.markdown, "proposal": d.proposal, "status": d.status}


@router.get("/boards/{bid}/drafts")
def drafts(bid: str, user: User = Depends(current_user), db: DB = Depends(get_db)):
    _board(db, bid, user)
    return [draft_dict(d) for d in db.scalars(
        select(AIDraft).where(AIDraft.board_id == bid).order_by(AIDraft.created_at.desc())).all()]


@router.post("/drafts/{did}/{decision}")
def decide(did: str, decision: str, request: Request, user: User = Depends(current_user), db: DB = Depends(get_db)):
    if decision not in {"accept", "discard"}:
        raise HTTPException(404, "Unknown action.")
    d = get_or_404(db, AIDraft, did, "Draft")
    d.status = "accepted" if decision == "accept" else "discarded"
    audit.record(db, f"ai.draft_{d.status}", "ai_draft", did, actor_id=user.id, request=request)
    db.commit()
    return {"ok": True}
