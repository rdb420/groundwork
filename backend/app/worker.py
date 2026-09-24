"""Background worker. Run alongside the API: `python -m app.worker`.

Picks queued jobs from the database, so it needs no broker; the claim step is a single UPDATE.
`--kinds transcribe_segment` runs a worker for transcription only, and
`--kinds profile_artifact` one for files only, so a large workbook never holds up the transcript
of a live session. With no --kinds, one worker does everything, transcription first.

A failed job waits before its next try (30 s, then 2 min), and fails for good after three. A job
left running by a crashed worker is picked up again.
"""
import argparse
import logging
import time
from datetime import timedelta

from sqlalchemy import case, or_, select, update

from . import audit, housekeeping, jobs, retention, scan
from .config import get_settings
from .db import SessionLocal, init_db
from .ingest import pipeline
from .models import Artifact, Job, TranscriptSegment
from .processing.text_extract import profile_document
from .processing.xlsx_profile import profile_workbook
from .security import utcnow
from .storage import get_storage, prefix_of
from .transcription import transcribe

log = logging.getLogger("groundwork.worker")
IMAGE = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".svg"}


def profile_artifact(db, aid: str):
    a = db.get(Artifact, aid)
    if not a or a.status in {"withdrawn", "purged", "quarantined"}:
        return
    a.status = "processing"
    db.commit()
    storage = get_storage()
    text = None
    with storage.local_copy(a.storage_key) as path:
        if scan.enabled():
            found = scan.scan_file(path)  # ScannerUnavailable fails the job, which retries later
            if found:
                a.status, a.scan, a.profile = "quarantined", "infected", {"type": "blocked", "summary": f"Blocked by the malware check ({found})."}
                audit.record(db, "artifact.quarantined", "artifact", aid, actor_type="system", detail={"signature": found})
                return
            a.scan = "clean"
        else:
            a.scan = "off"
        ext = path.suffix.lower()
        if ext in {".xlsx", ".xlsm"}:
            prof = profile_workbook(path)
        elif ext in IMAGE:
            prof = {"type": "image", "summary": "Image. Awaiting review."}
        else:
            read = profile_document(path)
            prof, text = read if read else ({"type": "file", "summary": f"{ext} file. Awaiting review."}, None)
    if text is not None:
        storage.put_bytes(prefix_of(a.storage_key) + "extracted.txt", text.encode(), "text/plain; charset=utf-8")
    a.profile, a.status = prof, "processed"
    audit.record(db, "artifact.processed", "artifact", aid, actor_type="system", detail={"summary": prof.get("summary")})
    if get_settings().pipeline_enabled and not a.board_id:
        pipeline.start(db, a)


def transcribe_segment(db, sid: str):
    seg = db.get(TranscriptSegment, sid)
    if not seg or not seg.audio_path:
        return
    with get_storage().local_copy(seg.audio_path) as path:
        result = transcribe(path)
    seg.text, seg.timings, seg.status = result.text, result.rows, "done"
    if get_settings().pipeline_enabled:
        pipeline.after_segment(db, seg)


HANDLERS = {"profile_artifact": profile_artifact, "transcribe_segment": transcribe_segment, **pipeline.STAGES}
# A live session's transcript comes first, then purges, then files in pipeline order.
PRIORITY = ["transcribe_segment", "purge_external", "profile_artifact", "convert_artifact", "transcribe_artifact",
            "ingest_recording", "index_chunks", "extract_entities", "project_graph"]
MAX_ATTEMPTS = 3
BACKOFF = [timedelta(seconds=30), timedelta(minutes=2)]
STALE_AFTER = timedelta(minutes=30)  # longer than any job should run


def claim(db, kinds: list[str] | None = None) -> Job | None:
    now = utcnow()
    q = select(Job).where(Job.status == "queued", or_(Job.run_after.is_(None), Job.run_after <= now))
    if kinds:
        q = q.where(Job.kind.in_(kinds))
    order = case({k: i for i, k in enumerate(PRIORITY)}, value=Job.kind, else_=len(PRIORITY))
    job = db.scalar(q.order_by(order, Job.created_at).limit(1))
    if not job:
        return None
    n = db.execute(update(Job).where(Job.id == job.id, Job.status == "queued")
                   .values(status="running", attempts=Job.attempts + 1, updated_at=utcnow())).rowcount
    db.commit()
    return db.get(Job, job.id) if n else None


def run_once(kinds: list[str] | None = None) -> bool:
    db = SessionLocal()
    try:
        job = claim(db, kinds)
        if not job:
            return False
        token = jobs.current_job_id.set(job.id)
        try:
            HANDLERS[job.kind](db, job.ref_id)
            job.status = "done"
        except Exception as e:  # keep the worker alive; record why
            log.exception("job %s failed", job.id)
            db.rollback()
            job = db.get(Job, job.id)
            job.status = "queued" if job.attempts < MAX_ATTEMPTS else "failed"
            job.run_after = utcnow() + BACKOFF[min(job.attempts, len(BACKOFF)) - 1] if job.status == "queued" else None
            job.error = str(e)[:2000]
            if job.kind == "profile_artifact":
                a = db.get(Artifact, job.ref_id)
                if a and a.status == "processing":
                    a.status = "failed" if job.status == "failed" else "received"  # waiting for its next try
            if job.kind == "transcribe_segment" and job.status == "failed":
                seg = db.get(TranscriptSegment, job.ref_id)
                if seg:
                    seg.status = "failed"
            if job.kind in pipeline.STAGES and job.status == "failed":
                pipeline.failed(db, job.kind, job.ref_id)
        finally:
            jobs.current_job_id.reset(token)
        job.updated_at = utcnow()
        db.commit()
        return True
    finally:
        db.close()


def run_retention() -> dict:
    with SessionLocal() as db:
        done = retention.run(db)
        db.commit()
    if any(done.values()):
        log.info("retention purged %s", done)
    return done


def reclaim(kinds: list[str] | None = None, older_than: timedelta = STALE_AFTER) -> int:
    """Put jobs left running by a crashed worker back in the queue."""
    with SessionLocal() as db:
        q = select(Job).where(Job.status == "running", Job.updated_at < utcnow() - older_than)
        if kinds:
            q = q.where(Job.kind.in_(kinds))
        stale = db.scalars(q).all()
        for job in stale:
            job.status = "queued" if job.attempts < MAX_ATTEMPTS else "failed"
            job.error = (job.error + "\nThe worker stopped while running this job.").strip()
            job.updated_at = utcnow()
        db.commit()
    if stale:
        log.warning("reclaimed %d job(s) left running", len(stale))
    return len(stale)


def run_housekeeping() -> dict:
    with SessionLocal() as db:
        done = housekeeping.run(db)
        db.commit()
    if any(done.values()):
        log.info("housekeeping %s", done)
    return done


def main():
    parser = argparse.ArgumentParser(description="Groundwork background worker")
    parser.add_argument("--kinds", help="comma-separated job kinds to run (default: all)", default="")
    args = parser.parse_args()
    kinds = [k for k in args.kinds.split(",") if k] or None
    unknown = set(kinds or []) - set(HANDLERS)
    if unknown:
        parser.error(f"unknown job kinds: {', '.join(sorted(unknown))}")
    logging.basicConfig(level=logging.INFO)
    init_db()
    # Anything still marked running for these kinds belonged to this worker before it stopped.
    reclaim(kinds, older_than=timedelta(0))
    upkeep = kinds is None or "profile_artifact" in kinds  # one worker does the daily and hourly jobs
    log.info("worker started for %s", ", ".join(kinds) if kinds else "all jobs")
    last_retention = last_upkeep = 0.0
    while True:
        if upkeep and time.time() - last_upkeep > 3600:
            last_upkeep = time.time()
            reclaim(kinds)
            run_housekeeping()
        if upkeep and get_settings().retention_auto and time.time() - last_retention > 86400:
            last_retention = time.time()
            run_retention()
        if not run_once(kinds):
            time.sleep(2)


if __name__ == "__main__":
    main()
