"""Phase 3 of the ingestion pipeline: Parakeet transcription, recordings becoming transcript
documents once every part is done, and uploaded audio."""
import json

import httpx
import pytest
from sqlalchemy import select

from app import httpclient
from app.config import get_settings
from app.db import SessionLocal
from app.ingest import pipeline
from app.models import Artifact, Chunk, Document, Recording
from app.storage import get_storage
from app.transcription import TranscriptionError, transcribe
from tests.conftest import sign_in
from tests.fakes import FakeParakeet
from tests.test_convert import drain, services  # noqa: F401
from tests.test_index import index  # noqa: F401

H = {"x-requested-with": "groundwork"}


@pytest.fixture
def parakeet(index, monkeypatch):  # noqa: F811
    fake = FakeParakeet()
    monkeypatch.setitem(httpclient.TRANSPORTS, "parakeet", httpx.MockTransport(fake))
    s = get_settings()
    monkeypatch.setattr(s, "transcription_provider", "parakeet")
    monkeypatch.setattr(s, "parakeet_url", "http://inference:7861")
    return fake


def test_parakeet_provider_reads_the_event_stream(parakeet, tmp_path):
    audio = tmp_path / "a.webm"
    audio.write_bytes(b"audio")
    t = transcribe(audio)
    assert t.rows == [[0.0, 4.5, "Part 1: I check the bank feed."], [5.0, 9.0, "Then I send a reminder."]]
    assert t.text == "Part 1: I check the bank feed. Then I send a reminder."
    assert parakeet.calls[0]["data"][0]["path"] == parakeet.uploads[0] and parakeet.calls[0]["data"][1] is None
    parakeet.fail = True
    with pytest.raises(TranscriptionError):
        transcribe(audio)


def test_a_recording_becomes_a_transcript_document_when_every_part_is_done(client, parakeet):
    sign_in(client, "lead@example.com.au")
    pid = client.post("/api/processes", headers=H, json={"name": "Recorded process"}).json()["id"]
    client.post("/api/artifacts", headers=H, files={"file": ("n.txt", b"notes")},
                data={"meta": json.dumps({"title": "Unsure notes", "personal_info": "unsure", "process_ids": [pid]})})
    b = client.post("/api/boards", headers=H, json={"title": "Arrears session", "process_id": pid}).json()
    rid = client.post(f"/api/boards/{b['id']}/recordings", headers=H, json={"consent_note": "Sam agreed"}).json()["id"]
    for seq in (0, 1):
        client.post(f"/api/recordings/{rid}/chunks?seq={seq}", headers=H, files={"file": ("c.webm", b"audio")})
    drain()
    with SessionLocal() as db:
        assert pipeline.current_document(db, "recording", rid) is None  # still recording
    client.post(f"/api/recordings/{rid}/end", headers=H)
    drain()
    with SessionLocal() as db:
        doc = pipeline.current_document(db, "recording", rid)
        assert doc is not None and doc.stage == "indexed" and doc.personal_info is True  # an unsure file on the process
        blocks = json.loads(get_storage().read_bytes(doc.content_list_key))
        times = [(b["start_s"], b["end_s"]) for b in blocks if b["type"] == "transcript"]
        assert times == [(0.0, 4.5), (5.0, 9.0), (30.0, 34.5), (35.0, 39.0)]  # part 2 starts 30 s in
        chunks = db.scalars(select(Chunk).where(Chunk.source_id == rid)).all()
        assert chunks and all(c.kind == "transcript" for c in chunks) and chunks[0].start_s == 0.0

        # Deleting the audio later keeps the transcript and its chunks.
        from app import retention
        retention.purge_audio(db, db.get(Recording, rid), actor_id=None, reason="test")
        db.commit()
        assert get_storage().exists(doc.content_list_key)
        assert db.scalars(select(Chunk).where(Chunk.source_id == rid)).all()


def test_uploaded_audio_is_transcribed_and_indexed(client, parakeet):
    sign_in(client, "staff@example.com.au")
    aid = client.post("/api/artifacts", headers=H, files={"file": ("voicemail.m4a", b"audio")},
                      data={"meta": json.dumps({"title": "Voicemail from owner", "personal_info": "no"})}).json()["id"]
    drain()
    with SessionLocal() as db:
        a = db.get(Artifact, aid)
        doc = db.scalar(select(Document).where(Document.source_id == aid))
        assert a.pipeline_status == "done" and doc.converter == "transcript:parakeet" and doc.stage == "indexed"


def test_failed_parts_still_let_the_transcript_through(client, parakeet):
    sign_in(client, "lead@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Flaky session"}).json()
    rid = client.post(f"/api/boards/{b['id']}/recordings", headers=H, json={"consent_note": "Sam agreed"}).json()["id"]
    client.post(f"/api/recordings/{rid}/chunks?seq=0", headers=H, files={"file": ("c.webm", b"audio")})
    drain()
    parakeet.fail = True
    client.post(f"/api/recordings/{rid}/chunks?seq=1", headers=H, files={"file": ("c.webm", b"audio")})
    client.post(f"/api/recordings/{rid}/end", headers=H)
    drain()
    with SessionLocal() as db:
        doc = pipeline.current_document(db, "recording", rid)
        assert doc is not None  # the part that failed for good doesn't hold up the rest
        assert len([b for b in json.loads(get_storage().read_bytes(doc.content_list_key)) if b["type"] == "transcript"]) == 2
