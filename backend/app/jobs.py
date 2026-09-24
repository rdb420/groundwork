"""Helpers for the job queue shared by the worker and the pipeline stages."""
from contextvars import ContextVar

from sqlalchemy import select, update
from sqlalchemy.orm import Session as DB

from .db import SessionLocal
from .models import Job
from .security import utcnow

current_job_id: ContextVar[str | None] = ContextVar("current_job_id", default=None)


def enqueue(db: DB, kind: str, ref_id: str) -> None:
    """Queue a job unless the same one is already waiting. The caller commits."""
    waiting = db.scalar(select(Job.id).where(Job.kind == kind, Job.ref_id == ref_id, Job.status == "queued"))
    if not waiting:
        db.add(Job(kind=kind, ref_id=ref_id))


def heartbeat() -> None:
    """Long stages (MinerU, Parakeet) call this while they wait, so the worker's stale-job check
    doesn't hand the job to someone else. Uses its own session so it never commits the caller's work."""
    job_id = current_job_id.get()
    if not job_id:
        return
    with SessionLocal() as db:
        db.execute(update(Job).where(Job.id == job_id).values(updated_at=utcnow()))
        db.commit()
