"""Hourly upkeep run by the worker: clear expired sign-in links and sessions."""
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session as DB

from .models import MagicToken, Session
from .security import utcnow
from .util import deleted


def run(db: DB) -> dict:
    """Tidy up. The caller commits."""
    now = utcnow()
    sessions = deleted(db, delete(Session).where(Session.expires_at < now))
    tokens = deleted(db, delete(MagicToken).where(MagicToken.expires_at < now - timedelta(days=1)))
    return {"sessions": sessions, "tokens": tokens}
