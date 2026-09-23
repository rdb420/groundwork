import os
import tempfile

import pytest

os.environ["GW_ENV_FILES"] = ""  # ignore the developer's .env
os.environ["GW_DATA_DIR"] = tempfile.mkdtemp(prefix="gw-test-")
os.environ["GW_ALLOWED_EMAIL_DOMAINS"] = "example.com.au"
os.environ["GW_ANALYST_EMAILS"] = "lead@example.com.au"
os.environ["GW_ADMIN_EMAILS"] = "boss@example.com.au"
os.environ["GW_AI_PROVIDER"] = "anthropic"
os.environ["GW_ANTHROPIC_API_KEY"] = "test"

from fastapi.testclient import TestClient  # noqa: E402

from app import mailer  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import auth as auth_router  # noqa: E402

SENT: dict[str, str] = {}


@pytest.fixture(scope="session")
def client():
    auth_router.send_magic_link = lambda to, link: SENT.__setitem__(to, link)
    mailer.send_magic_link = auth_router.send_magic_link
    with TestClient(app) as c:
        yield c


def sign_in(client, email):
    auth_router._hits.clear()  # tests sign in more often than the rate limit allows
    client.cookies.clear()
    r = client.post("/api/auth/request", json={"email": email})
    assert r.status_code == 200
    token = SENT[email].split("token=")[1]
    r = client.post("/api/auth/verify", json={"token": token})
    assert r.status_code == 200, r.text
    return token


def audited(action: str, entity_id: str | None = None) -> int:
    """How many audit events of this kind exist (for one record, if given)."""
    from sqlalchemy import func, select

    from app.db import SessionLocal
    from app.models import AuditEvent
    q = select(func.count()).select_from(AuditEvent).where(AuditEvent.action == action)
    if entity_id:
        q = q.where(AuditEvent.entity_id == entity_id)
    with SessionLocal() as db:
        return db.scalar(q) or 0
