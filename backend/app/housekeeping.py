"""Hourly upkeep run by the worker: clear expired sign-in links and sessions, and end recordings
nobody stopped (a closed laptop, a crashed browser)."""
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as DB

from . import audit
from .config import get_settings
from .models import MagicToken, Recording, Session, TranscriptSegment
from .security import aware, utcnow
from .util import deleted

ABANDONED_AFTER = timedelta(minutes=15)  # parts arrive every 30 seconds while recording


def end_abandoned_recordings(db: DB) -> int:
    now = utcnow()
    last_part = dict(db.execute(select(TranscriptSegment.recording_id, func.max(TranscriptSegment.created_at))
                                .group_by(TranscriptSegment.recording_id)).tuples().all())
    ended = 0
    for r in db.scalars(select(Recording).where(Recording.status == "recording")).all():
        last = last_part.get(r.id) or r.started_at
        if now - aware(last) > ABANDONED_AFTER:
            r.status, r.ended_at = "ended", aware(last)
            if get_settings().pipeline_enabled:
                from .ingest import pipeline
                pipeline.recording_ready(db, r.id)
            audit.record(db, "recording.ended", "recording", r.id, actor_type="system",
                         detail={"reason": "no audio for 15 minutes"})
            ended += 1
    return ended


def run(db: DB) -> dict:
    """Tidy up. The caller commits."""
    now = utcnow()
    sessions = deleted(db, delete(Session).where(Session.expires_at < now))
    tokens = deleted(db, delete(MagicToken).where(MagicToken.expires_at < now - timedelta(days=1)))
    return {"sessions": sessions, "tokens": tokens, "recordings_ended": end_abandoned_recordings(db)}
