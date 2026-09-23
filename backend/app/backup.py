"""Consistent backup of the database and every stored file.

Run on a schedule: `python -m app.backup` (or deploy/backup.sh from the host). The SQLite
online-backup API copies a consistent snapshot while the app keeps running. Copy the
resulting archive off the host; a backup on the same disk protects against mistakes, not
against losing the disk.

With GW_BACKUP_AGE_RECIPIENTS set, the archive is encrypted with age (https://age-encryption.org)
as it is written, to those public keys, and ends in .tar.gz.age. The host holds only public keys,
so a stolen backup or a compromised host can't be read without a private key kept elsewhere.
"""
import logging
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

from .config import get_settings

log = logging.getLogger("groundwork.backup")
TABLES = ("users", "artifacts", "boards", "audit_events")


class BackupError(RuntimeError):
    pass


def _recipients() -> list[str]:
    return [r.strip() for r in get_settings().backup_age_recipients.split(",") if r.strip()]


def _write_archive(out: IO[bytes], snap: Path, data_dir: Path) -> None:
    with tarfile.open(fileobj=out, mode="w|gz") as tar:
        tar.add(snap, arcname="groundwork.db")
        for sub in ("artifacts", "recordings"):
            if (data_dir / sub).exists():
                tar.add(data_dir / sub, arcname=sub)


def run() -> Path:
    s = get_settings()
    out_dir = s.data_dir / "backups"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    recipients = _recipients()
    archive = out_dir / (f"groundwork-{stamp}.tar.gz" + (".age" if recipients else ""))
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "groundwork.db"
        src = sqlite3.connect(s.db_url.removeprefix("sqlite:///"))
        dst = sqlite3.connect(snap)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        if recipients:
            age = shutil.which("age")
            if not age:
                raise BackupError("GW_BACKUP_AGE_RECIPIENTS is set but the age program isn't installed.")
            cmd = [age, *[a for r in recipients for a in ("-r", r)], "-o", str(archive)]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)  # noqa: S603  arguments are ours, no shell
            assert proc.stdin is not None
            try:
                _write_archive(proc.stdin, snap, s.data_dir)
            finally:
                proc.stdin.close()
            if proc.wait() != 0:
                archive.unlink(missing_ok=True)
                raise BackupError(f"age failed to encrypt the backup (exit {proc.returncode}).")
        else:
            log.warning("Backup is not encrypted. Set GW_BACKUP_AGE_RECIPIENTS before copying backups off the host.")
            with archive.open("wb") as f:
                _write_archive(f, snap, s.data_dir)
    cutoff = time.time() - s.backup_keep_days * 86400
    for old in [*out_dir.glob("groundwork-*.tar.gz"), *out_dir.glob("groundwork-*.tar.gz.age")]:
        if old.stat().st_mtime < cutoff:
            old.unlink()
    return archive


def _check_stream(stream: IO[bytes]) -> dict:
    """Read an archive as a stream: copy out the database, count the files, confirm the database reads."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "groundwork.db"
        files = 0
        found = False
        with tarfile.open(fileobj=stream, mode="r|gz") as tar:
            for m in tar:
                if m.name == "groundwork.db" and m.isfile():
                    src = tar.extractfile(m)
                    assert src is not None
                    db_path.write_bytes(src.read())
                    found = True
                elif m.isfile() and m.name.startswith("artifacts/"):
                    files += 1
        if not found:
            raise BackupError("The archive has no database in it.")
        con = sqlite3.connect(db_path)
        counts = {t: con.execute(f"select count(*) from {t}").fetchone()[0] for t in TABLES}  # noqa: S608  fixed names
        con.close()
    return {**counts, "artifact_files": files}


def restore_check(archive: Path, identity: Path | None = None) -> dict:
    """Open an archive and confirm the database inside reads. Test restores, not just backups.
    An encrypted archive needs an age identity (private key) file; without one, say so."""
    if archive.suffix != ".age":
        with archive.open("rb") as f:
            return _check_stream(f)
    identity = identity or (Path(get_settings().backup_age_identity_file) if get_settings().backup_age_identity_file else None)
    if not identity:
        return {"encrypted": True, "checked": False,
                "note": "Encrypted. Test a restore where the private key is kept: age -d -i key.txt FILE | tar tz"}
    age = shutil.which("age")
    if not age:
        raise BackupError("The age program isn't installed, so the encrypted backup can't be checked.")
    proc = subprocess.Popen([age, "-d", "-i", str(identity), str(archive)], stdout=subprocess.PIPE)  # noqa: S603
    assert proc.stdout is not None
    try:
        result = _check_stream(proc.stdout)
    finally:
        proc.stdout.close()
    if proc.wait() != 0:
        raise BackupError("age couldn't decrypt the backup with that key.")
    return {**result, "encrypted": True, "checked": True}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    path = run()
    print(path, restore_check(path))
