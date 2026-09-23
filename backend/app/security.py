"""Magic-link tokens, sessions, roles and a light CSRF guard.

Tokens and session secrets are random, sent once, and stored only as SHA-256 hashes.
"""
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from .config import get_settings
from .db import get_db
from .models import Session, User

COOKIE = "gw_session"
ROLE_RANK = {"contributor": 0, "analyst": 1, "admin": 2}


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def utcnow() -> datetime:
    return datetime.now(UTC)


def aware(dt: datetime) -> datetime:
    """SQLite drops tzinfo on read; treat stored values as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def role_for(email: str) -> str:
    s = get_settings()
    if email in s.admins:
        return "admin"
    if email in s.analysts:
        return "analyst"
    return "contributor"


def email_allowed(email: str) -> bool:
    domains = get_settings().domains
    return not domains or email.rsplit("@", 1)[-1] in domains


def create_session(db: DB, user: User) -> str:
    secret = new_secret()
    days = get_settings().session_days
    db.add(Session(token_hash=digest(secret), user_id=user.id, expires_at=utcnow() + timedelta(days=days)))
    return secret


def current_user(request: Request, db: DB = Depends(get_db)) -> User:
    secret = request.cookies.get(COOKIE)
    if not secret:
        raise HTTPException(401, "Sign in to continue.")
    sess = db.scalar(select(Session).where(Session.token_hash == digest(secret)))
    if not sess or aware(sess.expires_at) < utcnow():
        raise HTTPException(401, "Your session has ended. Sign in again.")
    user = sess.user
    if user.blocked:
        raise HTTPException(401, "Your access to Groundwork has been removed. Ask the AI lead if that's a mistake.")
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("x-requested-with") != "groundwork":
        raise HTTPException(403, "Request blocked. Reload the page and try again.")
    # Roles come from GW_ADMIN_EMAILS and GW_ANALYST_EMAILS, so removing an address takes effect
    # on the person's next request, not their next sign-in.
    user.role = role_for(user.email)
    user.last_seen_at = utcnow()
    db.commit()
    return user


def require(role: str):
    def dep(user: User = Depends(current_user)) -> User:
        if ROLE_RANK[user.role] < ROLE_RANK[role]:
            raise HTTPException(403, "You don't have access to this.")
        return user
    return dep


def can_see_all(user: User) -> bool:
    return ROLE_RANK[user.role] >= ROLE_RANK["analyst"]
