"""Withdrawing or purging a file removes it from everything the pipeline built: object storage,
Qdrant, the Neo4j graph, SQL chunks and entities, and the evidence on ontology proposals."""
import httpx
import pytest
from sqlalchemy import select

from app import httpclient, storage
from app.config import get_settings
from app.db import SessionLocal
from app.models import Artifact, Chunk, Document, EntityMention, OntologyCandidate
from tests.conftest import audited, sign_in
from tests.fakes import FakeS3
from tests.test_convert import drain, services  # noqa: F401
from tests.test_extract import LEASE, extraction, share  # noqa: F401
from tests.test_index import index  # noqa: F401

H = {"x-requested-with": "groundwork"}


@pytest.fixture
def everything(extraction, index, monkeypatch):  # noqa: F811
    s3 = FakeS3()
    monkeypatch.setitem(httpclient.TRANSPORTS, "s3", httpx.MockTransport(s3))
    s = get_settings()
    for k, v in {"storage_backend": "s3", "s3_endpoint": "http://supabase:8000/storage/v1/s3",
                 "s3_access_key": "k", "s3_secret_key": "s"}.items():
        monkeypatch.setattr(s, k, v)
    storage.get_storage.cache_clear()
    yield s3, index[1], extraction[1]
    storage.get_storage.cache_clear()


def _state(aid: str, s3: FakeS3, qdrant) -> dict:
    with SessionLocal() as db:
        return {"files": [k for k in s3.objects if k.startswith(f"artifacts/{aid}/")],
                "points": [p for p in qdrant.points.values() if p["payload"].get("source_id") == aid],
                "documents": db.scalars(select(Document).where(Document.source_id == aid)).all(),
                "chunks": db.scalars(select(Chunk).where(Chunk.source_id == aid)).all(),
                "mentions": db.scalars(select(EntityMention).where(EntityMention.source_id == aid)).all()}


def test_purge_removes_the_file_from_every_store(client, everything):
    s3, qdrant, neo = everything
    sign_in(client, "staff@example.com.au")
    aid = share(client, "lease.md", LEASE)
    drain()
    before = _state(aid, s3, qdrant)
    assert before["files"] and before["points"] and before["chunks"] and before["mentions"]
    assert any(k.endswith("document.md") for k in before["files"])  # the conversion lives in S3 too
    with SessionLocal() as db:
        cand = db.scalar(select(OntologyCandidate).where(OntologyCandidate.norm_label == "bond loan scheme"))
        assert cand is not None

    sign_in(client, "boss@example.com.au")
    assert client.post(f"/api/admin/artifacts/{aid}/purge", headers=H, json={"reason": "tenant ID inside"}).status_code == 200
    drain()
    after = _state(aid, s3, qdrant)
    assert after == {"files": [], "points": [], "documents": [], "chunks": [], "mentions": []}
    assert [p for s, p in neo.matching("MATCH (s:Source {id: $id}) OPTIONAL MATCH") if p["id"] == aid]
    with SessionLocal() as db:
        assert db.scalar(select(OntologyCandidate).where(OntologyCandidate.norm_label == "bond loan scheme")) is None
    assert audited("artifact.purge_cascaded", aid) == 1


def test_withdrawal_takes_a_file_out_of_search_and_the_graph_at_once(client, everything):
    s3, qdrant, neo = everything
    sign_in(client, "staff@example.com.au")
    aid = share(client, "lease.md", LEASE)
    drain()
    client.post(f"/api/artifacts/{aid}/withdraw", headers=H)
    drain()
    state = _state(aid, s3, qdrant)
    assert state["points"] == [] and state["files"] and state["chunks"]  # files and SQL wait for retention
    with SessionLocal() as db:  # and nothing processes it again
        from app.ingest import pipeline
        doc = pipeline.current_document(db, "artifact", aid)
        doc.index_key = ""
        pipeline.index_chunks(db, doc.id)
        db.commit()
    assert _state(aid, s3, qdrant)["points"] == []


def test_a_storage_outage_doesnt_stop_the_purge(client, everything):
    s3, qdrant, _ = everything
    sign_in(client, "staff@example.com.au")
    aid = share(client, "notes.md", "# Notes\n\nNothing personal.\n")
    drain()
    original = s3.__call__

    def down(request):
        return httpx.Response(503) if request.method in ("GET", "DELETE") and "list-type" in str(request.url) else original(request)

    httpclient.TRANSPORTS["s3"] = httpx.MockTransport(down)
    storage.get_storage.cache_clear()
    sign_in(client, "boss@example.com.au")
    assert client.post(f"/api/admin/artifacts/{aid}/purge", headers=H, json={"reason": "test"}).status_code == 200
    with SessionLocal() as db:
        a = db.get(Artifact, aid)
        assert a.status == "purged" and a.storage_key  # remembered for the retry
    httpclient.TRANSPORTS["s3"] = httpx.MockTransport(s3)
    storage.get_storage.cache_clear()
    drain()
    assert _state(aid, s3, qdrant)["files"] == []
    with SessionLocal() as db:
        assert db.get(Artifact, aid).storage_key == ""
