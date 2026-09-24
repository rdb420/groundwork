"""Queue every file shared before the pipeline was switched on (same as the Pipeline page's button).

    cd backend && uv run python -m app.ingest.backfill
"""
from sqlalchemy import select

from .. import audit, jobs
from ..config import get_settings
from ..db import SessionLocal, init_db
from ..models import Artifact


def main() -> None:
    if not get_settings().pipeline_enabled:
        raise SystemExit("Switch the pipeline on first (GW_PIPELINE_ENABLED=true).")
    init_db()
    with SessionLocal() as db:
        rows = db.scalars(select(Artifact).where(Artifact.board_id.is_(None), Artifact.status == "processed",
                                                 (Artifact.pipeline_status.is_(None)) | (Artifact.pipeline_status == ""))).all()
        for a in rows:
            a.pipeline_status = "queued"
            jobs.enqueue(db, "convert_artifact", a.id)
        audit.record(db, "pipeline.backfill", "system", actor_type="system", detail={"queued": len(rows)})
        db.commit()
    print(f"Queued {len(rows)} file(s).")


if __name__ == "__main__":
    main()
