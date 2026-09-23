from fastapi import Request
from sqlalchemy.orm import Session as DB

from .models import AuditEvent


def record(db: DB, action: str, entity: str, entity_id: str = "", *, actor_id: str | None = None,
           actor_type: str = "user", detail: dict | None = None, request: Request | None = None) -> None:
    """Add an audit event to the current transaction. The caller commits."""
    ip = request.client.host if request and request.client else ""
    db.add(AuditEvent(action=action, entity=entity, entity_id=entity_id, actor_id=actor_id,
                      actor_type=actor_type, detail=detail, ip=ip))
