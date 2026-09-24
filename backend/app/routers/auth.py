"""Email magic-link sign-in.

The emailed link opens a page in the web app; that page POSTs the token. Mail scanners
(Microsoft Safe Links, Mimecast) fetch GET links to check them, which would burn a
single-use token if a GET consumed it.
"""
import logging
import time
from collections import defaultdict, deque
from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from .. import audit
from ..config import get_settings
from ..db import get_db
from ..mailer import MailError, send_magic_link
from ..models import MagicToken, Session, User
from ..security import COOKIE, aware, create_session, current_user, digest, email_allowed, new_secret, role_for, utcnow

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("groundwork.auth")
_hits: dict[str, deque] = defaultdict(deque)


def _rate_limited(key: str, limit: int = 5, window: int = 600) -> bool:
    q, t = _hits[key], time.time()
    while q and q[0] < t - window:
        q.popleft()
    q.append(t)
    return len(q) > limit


class LinkRequest(BaseModel):
    email: EmailStr


class VerifyRequest(BaseModel):
    token: str


class ProfileUpdate(BaseModel):
    display_name: str = ""
    team: str = ""


GENERIC = {"message": "If that address can sign in, a link is on its way. Check your inbox."}


@router.post("/request")
def request_link(body: LinkRequest, request: Request, db: DB = Depends(get_db)):
    email = body.email.lower()
    ip = request.client.host if request.client else ""
    if _rate_limited(f"e:{email}") or _rate_limited(f"i:{ip}", limit=20):
        raise HTTPException(429, "Too many sign-in requests. Wait ten minutes and try again.")
    blocked = db.scalar(select(User.blocked).where(User.email == email))
    if not email_allowed(email) or blocked:
        audit.record(db, "auth.link_refused", "user", detail={"email": email, "blocked": bool(blocked)},
                     actor_type="system", request=request)
        db.commit()
        return GENERIC  # same reply either way, so the form can't be used to probe addresses
    s = get_settings()
    secret = new_secret()
    db.add(MagicToken(email=email, token_hash=digest(secret), requested_ip=ip,
                      expires_at=utcnow() + timedelta(minutes=s.magic_link_minutes)))
    audit.record(db, "auth.link_requested", "user", detail={"email": email}, actor_type="system", request=request)
    db.commit()
    try:
        send_magic_link(email, f"{s.public_base_url.rstrip('/')}/auth/verify?token={quote(secret)}")
    except MailError as e:
        log.warning("sign-in email to %s not sent: %s", email, e)
        audit.record(db, "auth.link_not_sent", "user", detail={"email": email, "reason": str(e)[:200]},
                     actor_type="system", request=request)
        db.commit()
        raise HTTPException(503, "We couldn't send the sign-in email just now. Try again in a few minutes, "
                                 "or tell the AI lead if it keeps happening.") from None
    return GENERIC


@router.post("/verify")
def verify(body: VerifyRequest, request: Request, response: Response, db: DB = Depends(get_db)):
    tok = db.scalar(select(MagicToken).where(MagicToken.token_hash == digest(body.token)))
    if not tok or tok.used_at or aware(tok.expires_at) < utcnow():
        raise HTTPException(400, "That link has expired or was already used. Request a new one.")
    tok.used_at = utcnow()
    user = db.scalar(select(User).where(User.email == tok.email))
    if not user:
        user = User(email=tok.email, role=role_for(tok.email))
        db.add(user)
        db.flush()
        audit.record(db, "user.created", "user", user.id, actor_id=user.id, request=request)
    elif user.blocked:
        raise HTTPException(403, "Your access to Groundwork has been removed. Ask the AI lead if that's a mistake.")
    else:
        user.role = role_for(user.email)
    secret = create_session(db, user)
    audit.record(db, "auth.signed_in", "user", user.id, actor_id=user.id, request=request)
    db.commit()
    s = get_settings()
    response.set_cookie(COOKIE, secret, httponly=True, secure=s.cookie_secure, samesite="lax",
                        max_age=s.session_days * 86400, path="/")
    return {"ok": True, "needs_profile": not user.display_name}


@router.post("/logout")
def logout(request: Request, response: Response, db: DB = Depends(get_db)):
    secret = request.cookies.get(COOKIE)
    if secret:
        sess = db.scalar(select(Session).where(Session.token_hash == digest(secret)))
        if sess:
            audit.record(db, "auth.signed_out", "user", sess.user_id, actor_id=sess.user_id, request=request)
            db.delete(sess)
            db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    s = get_settings()
    return {"id": user.id, "email": user.email, "display_name": user.display_name, "team": user.team,
            "role": user.role, "org_name": s.org_name, "app_name": s.app_name,
            "ai_enabled": s.ai_provider != "none", "transcription_enabled": s.transcription_provider != "none",
            "live_enabled": s.decision_provider != "none", "live_local": s.decision_local,
            "review_minutes": s.review_minutes, "live_auto_threshold": s.live_auto_threshold}


@router.put("/me")
def update_me(body: ProfileUpdate, request: Request, user: User = Depends(current_user), db: DB = Depends(get_db)):
    user = db.merge(user)
    user.display_name, user.team = body.display_name.strip()[:200], body.team.strip()[:200]
    audit.record(db, "user.profile_updated", "user", user.id, actor_id=user.id, request=request,
                 detail={"display_name": user.display_name, "team": user.team})
    db.commit()
    return {"ok": True}
