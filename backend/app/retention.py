"""Retention and purge. Withdrawn files and session audio are deleted from disk once they pass the
periods in config (see docs/PRIVACY.md). An admin can also purge a single file at once, for
example a scan of someone's licence shared by mistake.

A purge deletes the stored file, its sidecar and extracted text, and the first-read profile (which
can quote the file). The database row stays, marked purged, so the audit trail still says what
was shared, by whom and when it was removed. Transcripts stay with their map; they are the
evidence the map rests on. Copies inside older backups age out after GW_BACKUP_KEEP_DAYS.
"""
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from . import audit
from .config import get_settings
from .models import Artifact, Recording, TranscriptSegment
from .security import aware, utcnow


def _cutoff(days: int) -> datetime | None:
    return utcnow() - timedelta(days=days) if days > 0 else None


def due(db: DB) -> dict:
    """What the retention rules would purge now."""
    s = get_settings()
    files, audio = [], []
    if cut := _cutoff(s.retention_withdrawn_days):
        files = [a for a in db.scalars(select(Artifact).where(Artifact.status == "withdrawn")).all()
                 if a.withdrawn_at is not None and aware(a.withdrawn_at) < cut]
    if cut := _cutoff(s.retention_audio_days):
        audio = [r for r in db.scalars(select(Recording).where(Recording.status == "ended",
                                                               Recording.audio_purged_at.is_(None))).all()
                 if r.ended_at and aware(r.ended_at) < cut]
    return {"files": files, "audio": audio}


def purge_artifact(db: DB, a: Artifact, *, actor_id: str | None, reason: str) -> None:
    if a.status == "purged":
        return
    if a.stored_path:
        folder = Path(a.stored_path).parent
        artifacts_root = (get_settings().data_dir / "artifacts").resolve()
        if folder.resolve().is_relative_to(artifacts_root):  # never delete outside the store
            if folder.exists():
                shutil.rmtree(folder)
    a.status, a.purged_at, a.stored_path, a.profile = "purged", utcnow(), "", None
    audit.record(db, "artifact.purged", "artifact", a.id, actor_id=actor_id,
                 actor_type="user" if actor_id else "system", detail={"reason": reason})


def purge_audio(db: DB, r: Recording, *, actor_id: str | None, reason: str) -> None:
    folder = get_settings().data_dir / "recordings" / r.id
    if folder.exists():
        shutil.rmtree(folder)
    for seg in db.scalars(select(TranscriptSegment).where(TranscriptSegment.recording_id == r.id)).all():
        seg.audio_path = ""
    r.audio_purged_at = utcnow()
    audit.record(db, "recording.audio_purged", "recording", r.id, actor_id=actor_id,
                 actor_type="user" if actor_id else "system", detail={"reason": reason})


def run(db: DB, *, actor_id: str | None = None) -> dict:
    """Purge everything due. The caller commits."""
    d = due(db)
    for a in d["files"]:
        purge_artifact(db, a, actor_id=actor_id, reason="retention: withdrawn")
    for r in d["audio"]:
        purge_audio(db, r, actor_id=actor_id, reason="retention: session audio")
    return {"files": len(d["files"]), "audio": len(d["audio"])}
