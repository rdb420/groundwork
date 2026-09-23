import os
import stat
import sys
from pathlib import Path

from app import backup
from app.config import get_settings
from tests.conftest import sign_in

# A stand-in for the age program: "encrypts" by adding a header, "decrypts" by checking and
# removing it. It records the recipients it was given. Enough to test the plumbing without age.
FAKE_AGE = f"""#!{sys.executable}
import sys
args = sys.argv[1:]
if "-d" in args:
    data = open(args[-1], "rb").read()
    assert data.startswith(b"FAKEAGE\\n"), "not ours"
    sys.stdout.buffer.write(data[8:])
else:
    out = args[args.index("-o") + 1]
    recipients = [args[i + 1] for i, a in enumerate(args) if a == "-r"]
    open(out + ".recipients", "w").write(",".join(recipients))
    open(out, "wb").write(b"FAKEAGE\\n" + sys.stdin.buffer.read())
"""


def test_backup_round_trip(client):
    sign_in(client, "staff@example.com.au")
    path = backup.run()
    info = backup.restore_check(path)
    assert path.exists() and info["users"] >= 1


def test_encrypted_backup(client, tmp_path, monkeypatch):
    fake = tmp_path / "age"
    fake.write_text(FAKE_AGE)
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    s = get_settings()
    monkeypatch.setattr(s, "backup_age_recipients", "age1first, age1second")
    sign_in(client, "staff@example.com.au")
    path = backup.run()
    assert path.name.endswith(".tar.gz.age")
    assert Path(str(path) + ".recipients").read_text() == "age1first,age1second"
    assert path.read_bytes().startswith(b"FAKEAGE\n") and path.stat().st_size > 100
    unchecked = backup.restore_check(path)  # no private key on this host: say so, don't pretend
    assert unchecked["encrypted"] and not unchecked["checked"]
    key = tmp_path / "key.txt"
    key.write_text("AGE-SECRET-KEY-TEST")
    checked = backup.restore_check(path, identity=key)
    assert checked["checked"] and checked["users"] >= 1
