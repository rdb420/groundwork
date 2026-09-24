from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_Session = None


def engine():
    global _engine, _Session
    if _engine is None:
        url = get_settings().db_url
        is_sqlite = url.startswith("sqlite")
        # The API, the worker and the transcriber share one SQLite file; wait for a lock rather than fail.
        _engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30} if is_sqlite else {})
        if is_sqlite:
            @event.listens_for(_engine, "connect")
            def _pragmas(conn, _):
                cur = conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()
        _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def SessionLocal():
    engine()
    return _Session()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401  registers tables
    Base.metadata.create_all(engine())
    _add_missing_columns()
    _backfill_storage_keys()


def _add_missing_columns():
    """create_all makes new tables but never alters existing ones. For SQLite, add any column
    the model has and the table lacks, so an existing install picks up new fields on restart.
    Columns are only ever added here; renames and drops need a real migration."""
    from sqlalchemy import inspect, text
    eng = engine()
    if not str(eng.url).startswith("sqlite"):
        return
    insp = inspect(eng)
    with eng.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing:
                    ddl = col.type.compile(eng.dialect)
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl}'))


def _backfill_storage_keys():
    """Files stored before the storage layer kept absolute paths; turn them into keys under data_dir."""
    from pathlib import Path

    from sqlalchemy import text
    root = get_settings().data_dir.resolve()

    def key(path: str) -> str:
        try:
            return str(Path(path).resolve().relative_to(root))
        except ValueError:
            return ""

    with engine().begin() as conn:
        rows = conn.execute(text("SELECT id, stored_path FROM artifacts WHERE (storage_key IS NULL OR storage_key = '') "
                                 "AND stored_path IS NOT NULL AND stored_path != ''")).all()
        for aid, path in rows:
            conn.execute(text("UPDATE artifacts SET storage_key = :k WHERE id = :i"), {"k": key(path), "i": aid})
        rows = conn.execute(text("SELECT id, audio_path FROM transcript_segments WHERE audio_path LIKE '/%'")).all()
        for sid, path in rows:
            conn.execute(text("UPDATE transcript_segments SET audio_path = :k WHERE id = :i"), {"k": key(path), "i": sid})
