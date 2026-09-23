"""Domain model.

Artifacts are the evidence staff hand over. Processes are the catalogue those artifacts
link to. Boards are the mapping canvases. Every material action lands in audit_events.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def uid() -> str:
    return uuid.uuid4().hex


def now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    team: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(20), default="contributor")  # contributor | analyst | admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MagicToken(Base):
    __tablename__ = "magic_tokens"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(320), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_ip: Mapped[str] = mapped_column(String(64), default="")


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship()


class Process(Base):
    """A node in the process catalogue. Hierarchical: value chain > process > sub-process."""
    __tablename__ = "processes"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("processes.id"), nullable=True)
    owner_email: Mapped[str] = mapped_column(String(320), default="")
    status: Mapped[str] = mapped_column(String(20), default="proposed")  # proposed | confirmed | retired
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Artifact(Base):
    """One uploaded file plus the context its contributor gave it."""
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    # File facts
    original_filename: Mapped[str] = mapped_column(String(500))
    stored_path: Mapped[str] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(200), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), index=True)

    # Contributor metadata
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(40), default="other")  # spreadsheet | procedure | form | report | email | photo | other
    layer: Mapped[str] = mapped_column(String(20), default="unsure")  # declared | system | actual | workaround | unsure
    frequency: Mapped[str] = mapped_column(String(20), default="")  # daily | weekly | monthly | quarterly | adhoc
    source_system: Mapped[str] = mapped_column(String(200), default="")
    maintained_by: Mapped[str] = mapped_column(String(200), default="")
    personal_info: Mapped[str] = mapped_column(String(10), default="unsure")  # yes | no | unsure
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    if_it_disappeared: Mapped[str] = mapped_column(Text, default="")

    # Pipeline
    status: Mapped[str] = mapped_column(String(20), default="received")  # received | processing | processed | failed | withdrawn
    profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # output of processors
    board_id: Mapped[str | None] = mapped_column(ForeignKey("boards.id"), nullable=True)  # set for canvas images

    processes: Mapped[list["Process"]] = relationship(secondary="artifact_processes")
    uploader: Mapped[User] = relationship()


class ArtifactProcess(Base):
    __tablename__ = "artifact_processes"
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id", ondelete="CASCADE"), primary_key=True)
    process_id: Mapped[str] = mapped_column(ForeignKey("processes.id", ondelete="CASCADE"), primary_key=True)
    step_note: Mapped[str] = mapped_column(Text, default="")  # where in the process it is used


class Board(Base):
    """A mapping canvas. `doc` holds nodes, edges and viewport as saved by the client."""
    __tablename__ = "boards"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(300))
    process_id: Mapped[str | None] = mapped_column(ForeignKey("processes.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    version: Mapped[int] = mapped_column(Integer, default=1)
    doc: Mapped[dict] = mapped_column(JSON, default=lambda: {"nodes": [], "edges": [], "viewport": None})
    personal_info: Mapped[bool] = mapped_column(Boolean, default=False)
    # The living SOP or work instruction that the session reviewer keeps aligned with the map
    document_kind: Mapped[str] = mapped_column(String(10), default="sop")  # sop | wi
    document_markdown: Mapped[str] = mapped_column(Text, default="")
    document_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Session settings. Overview: standard path only. Detail: everything, one person's view at a time.
    session_pass: Mapped[str] = mapped_column(String(10), default="overview")  # overview | detail
    perspective: Mapped[str] = mapped_column(String(200), default="")  # whose view this map shows, if one person's
    # Business rules pulled out of the diagram: a list of decision tables (see live/rules.py)
    rules: Mapped[list | None] = mapped_column(JSON, nullable=True)
    process: Mapped[Process | None] = relationship()


class Recording(Base):
    """A mapping-session recording. Audio arrives in chunks so transcription can run near live."""
    __tablename__ = "recordings"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    board_id: Mapped[str] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    started_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_note: Mapped[str] = mapped_column(Text)  # who agreed to be recorded
    status: Mapped[str] = mapped_column(String(20), default="recording")  # recording | ended


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    recording_id: Mapped[str] = mapped_column(ForeignKey("recordings.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    audio_path: Mapped[str] = mapped_column(String(1000))
    text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | done | failed | skipped
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("recording_id", "seq"),)


class LiveUtterance(Base):
    """One finished sentence from a live session and what the decision model did with it."""
    __tablename__ = "live_utterances"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    board_id: Mapped[str] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(10), default="speech")  # speech | typed
    text: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(100), default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    answers: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # compact summary of the decisions
    ops: Mapped[list | None] = mapped_column(JSON, nullable=True)


class ParkingItem(Base):
    """Something heard that doesn't belong on the map yet: a problem, exception, workaround or rule
    raised during the overview pass. It becomes the agenda for the detail pass."""
    __tablename__ = "parking_items"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    board_id: Mapped[str] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    category: Mapped[str] = mapped_column(String(20))  # issue | workaround | exception | rule | question | detail
    text: Mapped[str] = mapped_column(Text)
    near_element: Mapped[str] = mapped_column(String(64), default="")  # element it was said about, if known
    utterance_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | placed | dismissed


class AIDraft(Base):
    """Model output. Always a proposal; a person accepts, edits or discards it."""
    __tablename__ = "ai_drafts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    board_id: Mapped[str] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    mode: Mapped[str] = mapped_column(String(20))  # sop | workflow | questions | review | combine
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(100))
    board_version: Mapped[int] = mapped_column(Integer)
    markdown: Mapped[str] = mapped_column(Text, default="")
    proposal: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {nodes:[], edges:[]} suggested additions
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | accepted | discarded


class Job(Base):
    """Work queue for the background worker."""
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(40))  # profile_artifact | transcribe_segment
    ref_id: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)  # queued | running | done | failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditEvent(Base):
    """Business audit trail: who did what, to which record, and when."""
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), default="user")  # user | system | ai
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(32), default="")
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
