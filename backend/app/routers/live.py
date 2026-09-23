"""Live mapping: one finished sentence in, proposed map changes out. Plus session settings, the
parking lot, rule tables, structure checks, the session reviewer, the living SOP or work
instruction, and combining one-person views."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from .. import access, audit
from ..ai.context import structure_checks
from ..ai.generate import GenerationRefused
from ..canvas import validate_doc
from ..config import get_settings
from ..db import get_db
from ..live import jev
from ..live.combine import combine_views
from ..live.interpret import build_request, plan
from ..live.review import run_review
from ..live.rules import normalise
from ..live.vocabulary import PARKING_CATEGORIES
from ..models import Board, LiveUtterance, ParkingItem, Process, User
from ..security import current_user, utcnow
from ..util import get_or_404
from .boards import board_dict, draft_dict

router = APIRouter(prefix="/api", tags=["live"])


class UtteranceIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    source: str = "speech"  # speech | typed
    mode: str = "listen"  # listen: interpret everything | command: only instructions to the map
    doc: dict  # the canvas as the facilitator sees it now, which may be ahead of the last autosave
    last_touched: str | None = None


class ReviewIn(BaseModel):
    doc: dict
    doc_kind: str = "sop"


class DocumentIn(BaseModel):
    markdown: str = Field(max_length=500_000)
    doc_kind: str = "sop"
    version: int  # the version the person started from


class SettingsIn(BaseModel):
    session_pass: str | None = None
    perspective: str | None = None


class ParkingIn(BaseModel):
    status: str | None = None
    category: str | None = None
    text: str | None = None


class ParkingNew(BaseModel):
    category: str = "detail"
    text: str = Field(min_length=1, max_length=2000)


class RulesIn(BaseModel):
    rules: list
    version: int  # the version the person started from


class ChecksIn(BaseModel):
    doc: dict


def _guard(board: Board):
    s = get_settings()
    if board.personal_info and not s.decision_local and not s.ai_allow_cloud_for_personal_info:
        raise HTTPException(409, "This map is marked as containing personal information, and live mapping uses a "
                                 "hosted decision model. Point GW_DECISION_URL at a local Jev-compatible server "
                                 "such as Laya, or untick personal information on the map.")


def parking_dict(p: ParkingItem) -> dict:
    return {"id": p.id, "category": p.category, "text": p.text, "near_element": p.near_element,
            "status": p.status, "created_at": p.created_at}


@router.post("/boards/{bid}/live/utterance")
def utterance(bid: str, body: UtteranceIn, request: Request, user: User = Depends(current_user),
              db: DB = Depends(get_db)):
    board = access.open_board(db, bid, user)
    _guard(board)
    if body.mode not in {"listen", "command"} or body.source not in {"speech", "typed"}:
        raise HTTPException(422, "Unknown live mode.")
    since = utcnow() - timedelta(minutes=10)
    recent = db.scalars(select(LiveUtterance.text).where(LiveUtterance.board_id == bid, LiveUtterance.created_at >= since)
                        .order_by(LiveUtterance.created_at.desc()).limit(3)).all()[::-1]
    text = body.text.strip()
    state, questions, ctx = build_request(text, list(recent), validate_doc(body.doc), body.last_touched, board.session_pass or "detail")
    try:
        answers, model, ms = jev.system_one(state, questions)
    except jev.DecisionError as e:
        raise HTTPException(502, str(e)) from e
    ops, parking, summary = plan(answers, ctx, body.mode, text)
    u = LiveUtterance(board_id=bid, created_by=user.id, source=body.source, text=text, model=model,
                      latency_ms=ms, answers=summary, ops=ops)
    db.add(u)
    db.flush()
    items = [ParkingItem(board_id=bid, utterance_id=u.id, **p) for p in parking]
    db.add_all(items)
    # Every sentence is recorded; the audit event says whether it changed or parked anything.
    audit.record(db, "live.ops_proposed" if ops or items else "live.heard", "board", bid, actor_id=user.id,
                 actor_type="ai", request=request,
                 detail={"utterance_id": u.id, "model": model, "parked": [p["category"] for p in parking],
                         "ops": [{k: o.get(k) for k in ("id", "op", "kind", "confidence", "auto")} for o in ops]})
    db.commit()
    return {"utterance_id": u.id, "ops": ops, "parking": [parking_dict(p) for p in items], "summary": summary,
            "model": model, "latency_ms": ms}


@router.get("/boards/{bid}/live/utterances")
def utterances(bid: str, user: User = Depends(current_user), db: DB = Depends(get_db)):
    access.open_board(db, bid, user)
    rows = db.scalars(select(LiveUtterance).where(LiveUtterance.board_id == bid)
                      .order_by(LiveUtterance.created_at.desc()).limit(200)).all()
    return [{"id": u.id, "text": u.text, "at": u.created_at, "source": u.source, "ops": u.ops or [],
             "latency_ms": u.latency_ms} for u in rows[::-1]]


@router.patch("/boards/{bid}/settings")
def settings(bid: str, body: SettingsIn, request: Request, user: User = Depends(current_user), db: DB = Depends(get_db)):
    b = access.open_board(db, bid, user)
    if body.session_pass is not None:
        if body.session_pass not in {"overview", "detail"}:
            raise HTTPException(422, "Choose the overview or the detail pass.")
        b.session_pass = body.session_pass
    if body.perspective is not None:
        b.perspective = body.perspective.strip()[:200]
    audit.record(db, "board.settings", "board", bid, actor_id=user.id, request=request,
                 detail=body.model_dump(exclude_none=True))
    db.commit()
    return board_dict(b)


@router.get("/boards/{bid}/parking")
def parking_list(bid: str, user: User = Depends(current_user), db: DB = Depends(get_db)):
    access.open_board(db, bid, user)
    rows = db.scalars(select(ParkingItem).where(ParkingItem.board_id == bid).order_by(ParkingItem.created_at)).all()
    return [parking_dict(p) for p in rows]


@router.post("/boards/{bid}/parking")
def parking_add(bid: str, body: ParkingNew, request: Request, user: User = Depends(current_user),
                db: DB = Depends(get_db)):
    access.open_board(db, bid, user)
    if body.category not in PARKING_CATEGORIES:
        raise HTTPException(422, "Unknown parking lot category.")
    p = ParkingItem(board_id=bid, category=body.category, text=body.text.strip())
    db.add(p)
    db.flush()
    audit.record(db, "parking.added", "parking_item", p.id, actor_id=user.id, request=request,
                 detail={"board_id": bid, "category": body.category})
    db.commit()
    return parking_dict(p)


@router.patch("/parking/{pid}")
def parking_update(pid: str, body: ParkingIn, request: Request, user: User = Depends(current_user),
                   db: DB = Depends(get_db)):
    p = get_or_404(db, ParkingItem, pid, "Parking lot item")
    access.open_board(db, p.board_id, user)
    if body.status is not None:
        if body.status not in {"open", "placed", "dismissed"}:
            raise HTTPException(422, "Unknown status.")
        p.status = body.status
    if body.category is not None:
        if body.category not in PARKING_CATEGORIES:
            raise HTTPException(422, "Unknown parking lot category.")
        p.category = body.category
    if body.text is not None and body.text.strip():
        p.text = body.text.strip()[:2000]
    audit.record(db, "parking.updated", "parking_item", pid, actor_id=user.id, request=request,
                 detail=body.model_dump(exclude_none=True))
    db.commit()
    return parking_dict(p)


@router.get("/boards/{bid}/rules")
def rules_get(bid: str, user: User = Depends(current_user), db: DB = Depends(get_db)):
    b = access.open_board(db, bid, user)
    return {"rules": b.rules or [], "version": b.rules_version or 0}


@router.put("/boards/{bid}/rules")
def rules_put(bid: str, body: RulesIn, request: Request, user: User = Depends(current_user), db: DB = Depends(get_db)):
    b = access.open_board(db, bid, user)
    if body.version != (b.rules_version or 0):
        raise HTTPException(409, "Someone else changed the rule tables. Reload them to see their changes, then redo yours.")
    b.rules = normalise(body.rules)
    b.rules_version = (b.rules_version or 0) + 1
    audit.record(db, "board.rules_saved", "board", bid, actor_id=user.id, request=request,
                 detail={"tables": len(b.rules), "rows": sum(len(t["rows"]) for t in b.rules), "version": b.rules_version})
    db.commit()
    return {"rules": b.rules, "version": b.rules_version}


@router.post("/boards/{bid}/checks")
def checks(bid: str, body: ChecksIn, user: User = Depends(current_user), db: DB = Depends(get_db)):
    b = access.open_board(db, bid, user)
    return structure_checks(validate_doc(body.doc), b.session_pass or "detail", b.rules)


@router.post("/boards/{bid}/live/review")
def review(bid: str, body: ReviewIn, request: Request, user: User = Depends(current_user), db: DB = Depends(get_db)):
    board = access.open_board(db, bid, user)
    if body.doc_kind not in {"sop", "wi"}:
        raise HTTPException(422, "Choose an SOP or a work instruction.")
    try:
        draft = run_review(db, board, user, validate_doc(body.doc), body.doc_kind)
    except GenerationRefused as e:
        raise HTTPException(409, str(e)) from e
    audit.record(db, "ai.review_created", "ai_draft", draft.id, actor_id=user.id, actor_type="ai", request=request,
                 detail={"board_id": bid, "provider": draft.provider, "model": draft.model,
                         "changes": len((draft.proposal or {}).get("changes", []))})
    db.commit()
    return draft_dict(draft)


@router.post("/processes/{pid}/combine")
def combine(pid: str, request: Request, user: User = Depends(current_user), db: DB = Depends(get_db)):
    process = get_or_404(db, Process, pid, "Process")
    try:
        board, draft = combine_views(db, process, user)
    except GenerationRefused as e:
        raise HTTPException(409, str(e)) from e
    audit.record(db, "ai.views_combined", "board", board.id, actor_id=user.id, actor_type="ai", request=request,
                 detail={"process_id": pid, "draft_id": draft.id, "sources": (draft.proposal or {}).get("sources", [])})
    db.commit()
    return board_dict(board)


@router.get("/boards/{bid}/document")
def get_document(bid: str, user: User = Depends(current_user), db: DB = Depends(get_db)):
    b = access.open_board(db, bid, user)
    return {"markdown": b.document_markdown, "doc_kind": b.document_kind, "updated_at": b.document_updated_at,
            "version": b.document_version or 0}


@router.put("/boards/{bid}/document")
def put_document(bid: str, body: DocumentIn, request: Request, user: User = Depends(current_user),
                 db: DB = Depends(get_db)):
    b = access.open_board(db, bid, user)
    if body.doc_kind not in {"sop", "wi"}:
        raise HTTPException(422, "Choose an SOP or a work instruction.")
    if body.version != (b.document_version or 0):
        raise HTTPException(409, "Someone else changed the document. Copy your changes, reload, then redo them.")
    b.document_markdown, b.document_kind, b.document_updated_at = body.markdown, body.doc_kind, utcnow()
    b.document_version = (b.document_version or 0) + 1
    audit.record(db, "board.document_saved", "board", bid, actor_id=user.id, request=request,
                 detail={"chars": len(body.markdown), "doc_kind": body.doc_kind, "version": b.document_version})
    db.commit()
    return {"ok": True, "updated_at": b.document_updated_at, "version": b.document_version}
