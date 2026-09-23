"""Background worker. Run alongside the API: `python -m app.worker`.

Picks queued jobs from the database, so it needs no broker. One worker process is enough
for an office; SQLite serialises writes and the claim step is a single UPDATE.
"""
import logging
import time
from pathlib import Path

from sqlalchemy import select, update

from . import audit
from .db import SessionLocal, init_db
from .models import Artifact, Job, TranscriptSegment
from .processing.text_extract import profile_document
from .processing.xlsx_profile import profile_workbook
from .security import utcnow
from .transcription import transcribe

log = logging.getLogger("groundwork.worker")
IMAGE = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".svg"}


def profile_artifact(db, aid: str):
    a = db.get(Artifact, aid)
    if not a or a.status == "withdrawn":
        return
    a.status = "processing"
    db.commit()
    path = Path(a.stored_path)
    ext = path.suffix.lower()
    if ext in {".xlsx", ".xlsm"}:
        prof = profile_workbook(path)
    elif ext in IMAGE:
        prof = {"type": "image", "summary": "Image. Awaiting review."}
    else:
        prof = profile_document(path) or {"type": "file", "summary": f"{ext} file. Awaiting review."}
    a.profile, a.status = prof, "processed"
    audit.record(db, "artifact.processed", "artifact", aid, actor_type="system", detail={"summary": prof.get("summary")})


def transcribe_segment(db, sid: str):
    seg = db.get(TranscriptSegment, sid)
    if not seg:
        return
    seg.text, seg.status = transcribe(Path(seg.audio_path)), "done"


HANDLERS = {"profile_artifact": profile_artifact, "transcribe_segment": transcribe_segment}


def claim(db) -> Job | None:
    job = db.scalar(select(Job).where(Job.status == "queued").order_by(Job.created_at).limit(1))
    if not job:
        return None
    n = db.execute(update(Job).where(Job.id == job.id, Job.status == "queued")
                   .values(status="running", attempts=Job.attempts + 1, updated_at=utcnow())).rowcount
    db.commit()
    return db.get(Job, job.id) if n else None


def run_once() -> bool:
    db = SessionLocal()
    try:
        job = claim(db)
        if not job:
            return False
        try:
            HANDLERS[job.kind](db, job.ref_id)
            job.status = "done"
        except Exception as e:  # keep the worker alive; record why
            log.exception("job %s failed", job.id)
            db.rollback()
            job = db.get(Job, job.id)
            job.status = "queued" if job.attempts < 3 else "failed"
            job.error = str(e)[:2000]
            if job.kind == "profile_artifact" and job.status == "failed":
                a = db.get(Artifact, job.ref_id)
                if a:
                    a.status = "failed"
            if job.kind == "transcribe_segment" and job.status == "failed":
                seg = db.get(TranscriptSegment, job.ref_id)
                if seg:
                    seg.status = "failed"
        job.updated_at = utcnow()
        db.commit()
        return True
    finally:
        db.close()


def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    log.info("worker started")
    while True:
        if not run_once():
            time.sleep(2)


if __name__ == "__main__":
    main()
