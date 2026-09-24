"""Phase 2 of the ingestion pipeline: chunking, embedding, indexing in Qdrant and searching."""
import json
import random

import httpx
import pytest
from sqlalchemy import select

from app import httpclient
from app.config import get_settings
from app.db import SessionLocal
from app.ingest import blocks as B
from app.ingest import chunker, pipeline, retrieve, tokens
from app.models import Artifact, Chunk, Document, User
from app.storage import get_storage
from tests.conftest import sign_in
from tests.fakes import FakeEmbed, FakeQdrant
from tests.test_convert import drain, services  # noqa: F401  the conversion fakes, reused

H = {"x-requested-with": "groundwork"}
WORDS = ("rent arrears tenant notice breach bond inspection room lease council approval payment plan owner "
         "manager bank feed reminder contractor repair invoice spreadsheet Monday Friday overdue").split()


@pytest.fixture
def index(services, monkeypatch):  # noqa: F811
    fake_embed, fake_qdrant = FakeEmbed(), FakeQdrant()
    monkeypatch.setitem(httpclient.TRANSPORTS, "embed", httpx.MockTransport(fake_embed))
    monkeypatch.setitem(httpclient.TRANSPORTS, "qdrant", httpx.MockTransport(fake_qdrant))
    s = get_settings()
    for k, v in {"embed_url": "http://embed:7860", "qdrant_url": "https://qdrant:6333", "qdrant_api_key": "qkey",
                 "extract_url": ""}.items():
        monkeypatch.setattr(s, k, v)
    return fake_embed, fake_qdrant


def share(client, name: str, text: str, **meta) -> str:
    r = client.post("/api/artifacts", headers=H, files={"file": (name, text.encode())},
                    data={"meta": json.dumps({"title": name, "personal_info": "no", **meta})})
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ---- Chunker ---------------------------------------------------------------------------

def _random_doc(rng: random.Random) -> list[dict]:
    out = []
    for _ in range(rng.randint(3, 25)):
        kind = rng.choice(["heading", "text", "text", "list", "table", "image"])
        words = lambda n: " ".join(rng.choice(WORDS) for _ in range(n))  # noqa: E731
        if kind == "heading":
            out.append({"type": "heading", "text": words(rng.randint(1, 30)), "level": rng.randint(1, 4)})
        elif kind == "text":
            lines = [words(rng.randint(1, 400)) + rng.choice([".", "", "!"]) for _ in range(rng.randint(1, 4))]
            out.append({"type": "text", "text": "\n".join(lines), "page": rng.randint(1, 9)})
        elif kind == "list":
            out.append({"type": "list", "items": [words(rng.randint(1, 60)) for _ in range(rng.randint(1, 8))]})
        elif kind == "table":
            cols = rng.randint(1, 12)
            out.append({"type": "table", "caption": words(rng.randint(0, 10)), "page": rng.randint(1, 9),
                        "rows": [[words(rng.randint(0, 20)) for _ in range(cols)] for _ in range(rng.randint(1, 30))]})
        else:
            out.append({"type": "image", "text": words(rng.randint(0, 200)), "page": rng.randint(1, 9)})
    return out


@pytest.mark.parametrize("seed", range(40))
def test_no_chunk_is_ever_over_budget(seed):
    rng = random.Random(seed)
    budget = rng.choice([64, 128])
    for p in chunker.chunk(_random_doc(rng), "A title of " + " ".join(rng.choice(WORDS) for _ in range(rng.randint(0, 40))),
                           budget):
        assert tokens.count(p.embed_text) <= budget
        assert p.text.strip()


def test_chunks_follow_headings_tables_and_pages():
    md = ("# Head lease\n\n## Rent\n\nRent is due every Monday.\nLate rent over 14 days gets a breach notice.\n\n"
          "## Rooms\n\n| Room | Rent |\n|---|---|\n" + "".join(f"| {i} | {200 + i} |\n" for i in range(60)) +
          "\n## Contacts\n\nCall the owner.\n")
    blocks = B.from_markdown(md)
    for b in blocks:
        b["page"] = 2
    pieces = chunker.chunk(blocks, "12 Smith St", 64)
    rent = [p for p in pieces if p.heading_path == ["Head lease", "Rent"]]
    assert len(rent) == 1 and rent[0].embed_text.startswith("12 Smith St > Head lease > Rent\n")
    tables = [p for p in pieces if p.kind == "table"]
    assert len(tables) > 1 and all(p.text.startswith("| Room | Rent |") for p in tables)
    assert all(p.page == 2 for p in pieces)
    assert pieces[-1].heading_path == ["Head lease", "Contacts"]  # never merged across a heading


def test_transcripts_keep_their_times():
    blocks = [{"type": "transcript", "text": f"sentence {i} about the bank feed.", "start_s": i * 5.0,
               "end_s": i * 5.0 + 4} for i in range(40)]
    pieces = chunker.chunk(blocks, "Session", 64)
    assert pieces[0].start_s == 0 and pieces[-1].end_s == 39 * 5 + 4
    assert all(a.end_s <= b.start_s + 5 for a, b in zip(pieces, pieces[1:], strict=False))


# ---- Indexing --------------------------------------------------------------------------

def test_indexing_builds_the_collection_and_is_idempotent(client, index):
    fake_embed, qd = index
    sign_in(client, "staff@example.com.au")
    aid = share(client, "arrears.md", "# Arrears\n\nCheck the bank feed every Monday.\n\n## Notices\n\n"
                                      "Late rent over 14 days gets a breach notice.\n")
    drain()
    with SessionLocal() as db:
        a = db.get(Artifact, aid)
        doc = db.scalar(select(Document).where(Document.source_id == aid))
        chunks = db.scalars(select(Chunk).where(Chunk.source_id == aid).order_by(Chunk.idx)).all()
        assert a.pipeline_status == "done" and doc.stage == "indexed" and doc.chunk_count == len(chunks) == 2
    config = qd.collections["gw_chunks_v1"]
    assert config["vectors"]["dense"] == {"size": 384, "distance": "Cosine"}
    assert config["vectors"]["colbert"]["multivector_config"] == {"comparator": "max_sim"}
    assert config["vectors"]["colbert"]["hnsw_config"] == {"m": 0} and config["sparse_vectors"] == {"splade": {}}
    assert qd.aliases == {"gw_chunks": "gw_chunks_v1"} and qd.api_keys == {"qkey"}
    assert {i["field_name"] for i in qd.indexes["gw_chunks_v1"]} >= {"artifact_id", "process_ids", "personal_info"}
    point = qd.points[chunks[0].id]
    assert point["payload"]["heading_path"] == ["Arrears"] and point["payload"]["personal_info"] is False
    assert len(point["vector"]["dense"]) == 384 and point["vector"]["colbert"]

    upserts = qd.upserts
    with SessionLocal() as db:
        pipeline.index_chunks(db, doc.id)  # nothing changed: no new embeddings or writes
        db.commit()
    assert qd.upserts == upserts

    # A shorter version replaces the chunks and removes the stale points.
    with SessionLocal() as db:
        doc = db.get(Document, doc.id)
        get_storage().put_bytes(doc.content_list_key, json.dumps([{"type": "text", "text": "Only one line now."}]).encode())
        doc.markdown_sha256 = "changed"
        pipeline.index_chunks(db, doc.id)
        db.commit()
    assert len([p for p in qd.points.values() if p["payload"]["artifact_id"] == aid]) == 1


def test_search_finds_the_right_chunk_and_respects_access(client, index):
    sign_in(client, "staff@example.com.au")
    mine = share(client, "breach.md", "# Breach notices\n\nLate rent over 14 days gets a breach notice from Dean.\n")
    share(client, "cleaning.md", "# Cleaning\n\nThe contractor cleans the kitchen every Friday.\n")
    gone = share(client, "old.md", "# Old\n\nBreach notice rules from last year.\n")
    client.post(f"/api/artifacts/{gone}/withdraw", headers=H)
    sign_in(client, "other@example.com.au")
    theirs = share(client, "breach2.md", "# Their notes\n\nBreach notice after 14 days late rent.\n")
    drain()
    with SessionLocal() as db:
        staff = db.scalar(select(User).where(User.email == "staff@example.com.au"))
        lead = db.scalar(select(User).where(User.email == "lead@example.com.au"))
        hits = retrieve.search(db, staff, "when does a breach notice go out for late rent", k=5)
        assert hits and hits[0]["artifact_id"] == mine and hits[0]["heading_path"] == ["Breach notices"]
        found = {h["artifact_id"] for h in hits}
        assert theirs not in found  # a contributor only finds their own files
        assert gone not in found  # withdrawn files never come back
        if lead is None:
            sign_in(client, "lead@example.com.au")
            lead = db.scalar(select(User).where(User.email == "lead@example.com.au"))
        assert theirs in {h["artifact_id"] for h in retrieve.search(db, lead, "breach notice late rent", k=10)}
