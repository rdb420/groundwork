"""Ontology candidates review and the pipeline admin routes."""

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Artifact, Document, Job, OntologyCandidate
from tests.conftest import audited, sign_in
from tests.test_convert import drain, services  # noqa: F401
from tests.test_extract import LEASE, extraction, share  # noqa: F401
from tests.test_index import index  # noqa: F401

H = {"x-requested-with": "groundwork"}


def test_analysts_review_and_export_candidates(client, extraction):  # noqa: F811
    sign_in(client, "staff@example.com.au")
    share(client, "lease.md", LEASE)
    drain()
    assert client.get("/api/ontology/candidates").status_code == 403
    sign_in(client, "lead@example.com.au")
    rows = client.get("/api/ontology/candidates").json()
    bond = next(c for c in rows if c["label"] == "Bond Loan Scheme")
    assert bond["evidence"] and "Bond Loan Scheme" in bond["evidence"][0]["text"]
    assert client.post(f"/api/ontology/candidates/{bond['id']}", headers=H, json={"action": "maybe"}).status_code == 422
    assert client.post(f"/api/ontology/candidates/{bond['id']}", headers=H,
                       json={"action": "merge", "merged_into_iri": "pbo:Nonsense"}).status_code == 422
    r = client.post(f"/api/ontology/candidates/{bond['id']}", headers=H,
                    json={"action": "accept", "parent_iri": "pbo:Service", "note": "A state scheme we deal with"})
    assert r.status_code == 200 and r.json()["status"] == "accepted" and audited("ontology.candidate_accepted", bond["id"]) == 1
    terms = client.get("/api/ontology/terms?q=tenancy").json()
    assert any(t["iri"] == "pbo:ResidentialTenancyAgreement" for t in terms)

    out = client.post("/api/ontology/candidates-export", headers=H).json()
    assert out["count"] >= 1 and "pbo:BondLoanScheme" in out["yaml"] and "Bond Loan Scheme" in out["markdown"]
    assert "lease.md" in out["markdown"]  # each item cites where it was seen
    assert client.post("/api/ontology/candidates-export", headers=H).status_code == 409  # nothing new since
    with SessionLocal() as db:
        assert db.get(OntologyCandidate, bond["id"]).status == "exported"
    assert audited("ontology.candidates_exported") >= 1


def test_admins_see_the_pipeline_and_reprocess(client, extraction):  # noqa: F811
    sign_in(client, "staff@example.com.au")
    aid = share(client, "lease.md", LEASE)
    drain()
    sign_in(client, "lead@example.com.au")
    assert client.get("/api/admin/pipeline").status_code == 403
    sign_in(client, "boss@example.com.au")
    status = client.get("/api/admin/pipeline").json()
    assert status["enabled"] and status["services"]["graph"] and status["files"].get("done", 0) >= 1

    assert client.post(f"/api/admin/artifacts/{aid}/reprocess", headers=H, json={"stage": "sideways"}).status_code == 422
    for stage in ("extract", "index", "convert"):
        assert client.post(f"/api/admin/artifacts/{aid}/reprocess", headers=H, json={"stage": stage}).status_code == 200
    assert audited("pipeline.reprocess", aid) == 3
    with SessionLocal() as db:
        kinds = {j.kind for j in db.scalars(select(Job).where(Job.status == "queued")).all()}
    assert {"extract_entities", "index_chunks", "convert_artifact"} <= kinds
    drain()
    with SessionLocal() as db:
        docs = db.scalars(select(Document).where(Document.source_id == aid)).all()
        assert len(docs) == 2 and sum(d.is_current for d in docs) == 1  # converted again as a new version
        assert db.get(Artifact, aid).pipeline_status == "done"

    r = client.post("/api/admin/pipeline/reprocess", headers=H, json={"stage": "graph"})
    assert r.status_code == 200 and r.json()["queued"] >= 1 and audited("pipeline.reprocess_all") >= 1
    drain()


def test_backfill_queues_files_shared_before_the_pipeline(client, extraction, monkeypatch):  # noqa: F811
    monkeypatch.setattr(get_settings(), "pipeline_enabled", False)
    sign_in(client, "staff@example.com.au")
    aid = share(client, "old.md", "# Old notes\n\nFrom before the pipeline.\n")
    drain()
    sign_in(client, "boss@example.com.au")
    assert client.post("/api/admin/pipeline/backfill", headers=H).status_code == 409
    monkeypatch.setattr(get_settings(), "pipeline_enabled", True)
    r = client.post("/api/admin/pipeline/backfill", headers=H)
    assert r.status_code == 200 and r.json()["queued"] >= 1
    drain()
    with SessionLocal() as db:
        assert db.get(Artifact, aid).pipeline_status == "done"


def test_topics_link_to_concepts_or_become_proposals(client, extraction, monkeypatch):  # noqa: F811
    from app.models import ChunkTopic, Topic
    monkeypatch.setattr(get_settings(), "topics_min_chunks", 3)
    sign_in(client, "staff@example.com.au")
    for i, text in enumerate(["Gross lease terms for the shop.", "Gross lease renewal notes.",
                              "Laundry roster for residents.", "Laundry machine repairs."]):
        share(client, f"t{i}.md", f"# Note {i}\n\n{text}\n")
    drain()
    sign_in(client, "boss@example.com.au")
    assert client.post("/api/admin/pipeline/topics", headers=H).status_code == 200
    drain()
    with SessionLocal() as db:
        topics = db.scalars(select(Topic)).all()
        assert topics and db.scalars(select(ChunkTopic)).all()
        proposals = db.scalars(select(OntologyCandidate).where(OntologyCandidate.kind == "concept")).all()
        assert proposals  # "laundry" is no ontology concept, so it waits for an analyst
    assert audited("pipeline.topics") == 1
