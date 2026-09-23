"""Consistent backup of the database and every stored file.

Run on a schedule: `python -m app.backup` (or deploy/backup.sh from the host). The SQLite
online-backup API copies a consistent snapshot while the app keeps running. Copy the
resulting archive off the host; a backup on the same disk protects against mistakes, not
against losing the disk.
"""
import sqlite3
import tarfile
import tempfile
import time
from datetime import datetime
from pathlib import Path

from .config import get_settings


def run() -> Path:
    s = get_settings()
    out_dir = s.data_dir / "backups"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = out_dir / f"groundwork-{stamp}.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "groundwork.db"
        src = sqlite3.connect(s.db_url.removeprefix("sqlite:///"))
        dst = sqlite3.connect(snap)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(snap, arcname="groundwork.db")
            for sub in ("artifacts", "recordings"):
                if (s.data_dir / sub).exists():
                    tar.add(s.data_dir / sub, arcname=sub)
    cutoff = time.time() - s.backup_keep_days * 86400
    for old in out_dir.glob("groundwork-*.tar.gz"):
        if old.stat().st_mtime < cutoff:
            old.unlink()
    return archive


def restore_check(archive: Path) -> dict:
    """Open an archive and confirm the database inside reads. Test restores, not just backups."""
    with tempfile.TemporaryDirectory() as tmp, tarfile.open(archive) as tar:
        tar.extract("groundwork.db", tmp, filter="data")
        con = sqlite3.connect(Path(tmp) / "groundwork.db")
        counts = {t: con.execute(f"select count(*) from {t}").fetchone()[0]
                  for t in ("users", "artifacts", "boards", "audit_events")}
        con.close()
        files = sum(1 for m in tar.getmembers() if m.isfile() and m.name.startswith("artifacts/"))
    return {**counts, "artifact_files": files}


if __name__ == "__main__":
    path = run()
    print(path, restore_check(path))
