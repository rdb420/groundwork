"""Storage layer: SigV4 signing, the S3 backend against a fake server, and uploads, downloads and
purges working the same on either backend."""
import json
from datetime import UTC, datetime

import httpx
import pytest

from app import httpclient, storage
from app.config import get_settings
from app.s3 import EMPTY_SHA256, sign
from tests.conftest import sign_in
from tests.fakes import FakeS3

H = {"x-requested-with": "groundwork"}
AWS = dict(access_key="AKIAIOSFODNN7EXAMPLE", secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
           region="us-east-1", now=datetime(2013, 5, 24, tzinfo=UTC))


def test_sigv4_matches_the_published_examples():
    # AWS's "Signature Calculations for the Authorization Header" examples (GET Object, GET Bucket).
    h = sign("GET", "https://examplebucket.s3.amazonaws.com/test.txt", {"Range": "bytes=0-9"}, EMPTY_SHA256, **AWS)
    assert h["authorization"].endswith("Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41")
    h = sign("GET", "https://examplebucket.s3.amazonaws.com/?max-keys=2&prefix=J", {}, EMPTY_SHA256, **AWS)
    assert h["authorization"].endswith("Signature=34b48302e7b5fa45bde8084f4b7868a86f0a534bc59db6670ed5711ef69dc6f7")


@pytest.fixture
def s3(monkeypatch):
    fake = FakeS3()
    monkeypatch.setitem(httpclient.TRANSPORTS, "s3", httpx.MockTransport(fake))
    s = get_settings()
    for k, v in {"storage_backend": "s3", "s3_endpoint": "http://supabase:8000/storage/v1/s3",
                 "s3_access_key": "key", "s3_secret_key": "secret"}.items():
        monkeypatch.setattr(s, k, v)
    storage.get_storage.cache_clear()
    yield fake
    storage.get_storage.cache_clear()


def test_s3_backend_round_trip(s3, tmp_path):
    st = storage.get_storage()
    f = tmp_path / "a.txt"
    f.write_text("hello")
    st.put_file("artifacts/x/original.txt", f)
    st.put_bytes("artifacts/x/extracted.txt", b"hello again")
    for i in range(3):
        st.put_bytes(f"artifacts/x/v1/images/{i}.png", b"img")
    st.put_bytes("artifacts/y/original.txt", b"keep")
    assert st.exists("artifacts/x/original.txt") and not st.exists("artifacts/x/nope.txt")
    assert st.read_bytes("artifacts/x/extracted.txt", 5) == b"hello"
    with st.local_copy("artifacts/x/original.txt") as p:
        assert p.read_text() == "hello"
    assert st.delete_prefix("artifacts/x/") == 5  # listed over three pages
    assert list(s3.objects) == ["artifacts/y/original.txt"]
    assert all(r.url.path.startswith("/storage/v1/s3/groundwork") for r in s3.requests)


def test_keys_cannot_leave_the_store():
    for bad in ("../etc/passwd", "artifacts/../../x", "/abs/path", "other/x"):
        with pytest.raises(ValueError):
            storage.check_key(bad)


def test_upload_download_and_purge_through_s3(client, s3):
    sign_in(client, "staff@example.com.au")
    r = client.post("/api/artifacts", headers=H, files={"file": ("notes.txt", b"hello s3", "text/plain")},
                    data={"meta": json.dumps({"title": "S3 notes", "personal_info": "no"})})
    aid = r.json()["id"]
    assert f"artifacts/{aid}/original.txt" in s3.objects and f"artifacts/{aid}/metadata.json" in s3.objects
    d = client.get(f"/api/artifacts/{aid}/file")
    assert d.status_code == 200 and d.content == b"hello s3"
    assert d.headers["content-disposition"].startswith("attachment") and "sandbox" in d.headers["content-security-policy"]
    sign_in(client, "boss@example.com.au")
    assert client.post(f"/api/admin/artifacts/{aid}/purge", headers=H, json={"reason": "test"}).status_code == 200
    assert not [k for k in s3.objects if k.startswith(f"artifacts/{aid}/")]


def test_old_absolute_paths_become_keys(tmp_path):
    from app.db import SessionLocal, _backfill_storage_keys
    from app.models import Artifact, User
    root = get_settings().data_dir.resolve()
    with SessionLocal() as db:
        u = db.query(User).first()
        db.add(Artifact(id="legacy1", uploaded_by=u.id, original_filename="a.txt", sha256="", title="t",
                        stored_path=str(root / "artifacts/2026/09/legacy1/original.txt"), storage_key=""))
        db.commit()
    _backfill_storage_keys()
    with SessionLocal() as db:
        assert db.get(Artifact, "legacy1").storage_key == "artifacts/2026/09/legacy1/original.txt"
