"""Phase 4 of the ingestion pipeline: ontology-closed extraction (GLiNER2 + Jev), candidates for
what the ontology lacks, the personal-information guard, and projection into Neo4j."""
import json
import re

import httpx
import pytest
from sqlalchemy import select

from app import httpclient
from app.config import get_settings
from app.db import SessionLocal
from app.ingest import extract, graph
from app.ingest.ontology import load
from app.live import jev
from app.models import Artifact, ChunkTag, Document, EntityMention, OntologyCandidate, RelationAssertion
from tests.conftest import sign_in
from tests.fakes import FakeExtractor, FakeNeo4j
from tests.test_convert import drain, services  # noqa: F401
from tests.test_index import index  # noqa: F401

H = {"x-requested-with": "groundwork"}
LEASE = ("# Residential tenancy agreement\n\nSam Nguyen signed the residential tenancy agreement with YSH Pty Ltd "
         "for the dwelling. YSH will send a head lease summary. The Bond Loan Scheme covers the bond.\n")


class FakeJev:
    """Picks the option whose label contains a keyword; otherwise 'none'. Records every question."""

    def __init__(self, prefer: tuple[str, ...] = ("Tenant / lessee",), other_for: str = ""):
        self.prefer = prefer
        self.other_for = other_for
        self.calls: list[dict] = []

    def __call__(self, state, questions, *, target=None):
        self.calls.append({"state": state, "questions": questions, "target": target})
        answers = {}
        for key, q in questions.items():
            opts = q["criteria"]
            assert len(opts) <= get_settings().decision_max_options, q["instructions"]
            if self.other_for and self.other_for in q["instructions"]:
                pick = "other"
            else:
                pick = next((k for k, label in opts.items() if any(p in label for p in self.prefer)), None)
                pick = pick or next((k for k, label in opts.items() if label.startswith("One of:")
                                     and any(p in label for p in self.prefer)), None)
                pick = pick or next((k for k in opts if k.startswith("c")), "none")
            answers[key] = {"type": "choice", "choice": pick, "confidence": 0.9}
        return answers, "jev-test", 5


@pytest.fixture
def extraction(index, monkeypatch):  # noqa: F811
    o = load()
    lexicon = {o.label("pbo:Person"): ["Sam Nguyen"], o.label("pbo:Organisation"): ["YSH Pty Ltd", "YSH"],
               o.label("pbo:ResidentialTenancyAgreement"): ["residential tenancy agreement"],
               o.label("pbo:Dwelling"): ["dwelling"], extract.CATCH_ALL: ["Bond Loan Scheme"]}
    fake, neo, fake_jev = FakeExtractor(lexicon), FakeNeo4j(), FakeJev()
    monkeypatch.setitem(httpclient.TRANSPORTS, "extract", httpx.MockTransport(fake))
    monkeypatch.setitem(httpclient.TRANSPORTS, "neo4j", httpx.MockTransport(neo))
    monkeypatch.setattr(jev, "system_one", fake_jev)
    s = get_settings()
    for k, v in {"extract_url": "http://inference:7870", "neo4j_url": "http://neo4j:7474", "neo4j_password": "pw",
                 "decision_provider": "openrouter", "decision_is_local": False,
                 "ai_allow_cloud_for_personal_info": False, "extract_decision_url": ""}.items():
        monkeypatch.setattr(s, k, v)
    graph._loaded.clear()
    return fake, neo, fake_jev


def share(client, name: str, text: str, pi: str = "no") -> str:
    r = client.post("/api/artifacts", headers=H, files={"file": (name, text.encode())},
                    data={"meta": json.dumps({"title": name, "personal_info": pi})})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_every_relation_question_fits_the_option_limit():
    o = load()
    limit = get_settings().decision_max_options
    classes = o.span_classes()
    for a in classes:
        for b in classes:
            options = o.relation_options(a, b)
            groups = [options[i:i + extract.MAX_GROUP] for i in range(0, len(options), extract.MAX_GROUP)]
            assert len(groups) + 2 <= limit  # first step: groups plus "none" and "another"
            assert all(len(g) + 2 <= limit for g in groups)  # second step


def test_a_lease_becomes_entities_roles_and_a_graph(client, extraction):
    fake, neo, fake_jev = extraction
    sign_in(client, "staff@example.com.au")
    aid = share(client, "lease.md", LEASE)
    drain()
    o = load()
    with SessionLocal() as db:
        a = db.get(Artifact, aid)
        doc = db.scalar(select(Document).where(Document.source_id == aid))
        mentions = db.scalars(select(EntityMention).where(EntityMention.source_id == aid)).all()
        relations = db.scalars(select(RelationAssertion).where(RelationAssertion.source_id == aid)).all()
        assert a.pipeline_status == "done" and doc.stage == "graphed" and doc.status == "ok"
        kinds = {(m.surface, m.class_iri) for m in mentions}
        assert ("Sam Nguyen", "pbo:Person") in kinds and ("YSH Pty Ltd", "pbo:Organisation") in kinds
        ysh = {m.entity_key for m in mentions if m.surface.startswith("YSH")}
        assert len(ysh) == 1  # "YSH" and "YSH Pty Ltd" are the same organisation
        tenant = [r for r in relations if r.role_iri == "pbo:Role_Tenant"] or \
                 [r for r in relations if o.label(r.role_iri).startswith("Tenant")]
        assert tenant, [(r.property_iri, r.role_iri) for r in relations]
        # The catch-all span is a proposal, not an entity.
        cand = db.scalar(select(OntologyCandidate).where(OntologyCandidate.norm_label == "bond loan scheme"))
        from app.models import Chunk
        mine = set(db.scalars(select(Chunk.id).where(Chunk.source_id == aid)).all())
        assert cand is not None and cand.kind == "class" and mine & set(cand.evidence)
        assert not [m for m in mentions if m.surface == "Bond Loan Scheme"]
    # Jev read the chunk as data in state, and every question stayed within the limit (FakeJev asserts it).
    assert fake_jev.calls and all("text" in c["state"] for c in fake_jev.calls)
    # The graph: ontology loaded, entities labelled by class, the Participation pattern, no chunk text.
    assert neo.matching("MERGE (v:OntologyVersion") and neo.auth == {"Basic bmVvNGo6cHc="}
    assert neo.matching("SET e:Person") and neo.matching("MERGE (ctx)-[x:hasParticipation]->(p)")
    for stmt, params in neo.statements:
        for label in re.findall(r"SET e:(\S+),", stmt) + re.findall(r"-\[x:(\w+)\]->", stmt):
            assert graph.NAME.match(label)
        assert LEASE[40:80] not in json.dumps(params)  # chunk text never goes into the graph


def test_reprocessing_replaces_the_graph_and_candidates_count_up(client, extraction):
    fake, neo, _ = extraction
    sign_in(client, "staff@example.com.au")
    first = share(client, "lease1.md", LEASE)
    drain()
    loads = len(neo.matching("MERGE (v:OntologyVersion"))
    second = share(client, "lease2.md", LEASE.replace("Sam Nguyen", "Priya Shah"))
    drain()
    assert len(neo.matching("MERGE (v:OntologyVersion")) == loads  # loaded once per version
    removals = [p["id"] for s, p in neo.matching("MATCH (s:Source {id: $id}) OPTIONAL MATCH")]
    assert first in removals and second in removals  # each projection replaces the source's old part
    with SessionLocal() as db:
        cand = db.scalar(select(OntologyCandidate).where(OntologyCandidate.norm_label == "bond loan scheme"))
        assert cand.occurrences >= 2 and len(cand.evidence) >= 2


def test_personal_files_wait_for_a_local_decision_model(client, extraction, monkeypatch):
    fake, neo, fake_jev = extraction
    sign_in(client, "staff@example.com.au")
    aid = share(client, "tenant-file.md", LEASE, pi="unsure")
    drain()
    with SessionLocal() as db:
        a = db.get(Artifact, aid)
        doc = db.scalar(select(Document).where(Document.source_id == aid))
        assert not fake_jev.calls  # the hosted decision model never saw it
        assert doc.status == "partial" and "local decision model" in doc.note and a.pipeline_status == "partial"
        assert db.scalars(select(EntityMention).where(EntityMention.source_id == aid)).all()  # entities kept
        assert not db.scalars(select(RelationAssertion).where(RelationAssertion.source_id == aid)).all()
    assert neo.matching("s.personal_info = $pi")

    # A local extraction model is allowed; the next run fills in the relationships.
    monkeypatch.setattr(get_settings(), "extract_decision_url", "http://laya:8080/v1/systemone")
    monkeypatch.setattr(get_settings(), "extract_decision_is_local", True)
    with SessionLocal() as db:
        doc = db.scalar(select(Document).where(Document.source_id == aid))
        from app.ingest import pipeline
        pipeline.extract_entities(db, doc.id)
        db.commit()
        assert fake_jev.calls and fake_jev.calls[0]["target"][0] == "http://laya:8080/v1/systemone"
        assert db.get(Document, doc.id).status == "ok"


def test_unstated_relationships_become_candidates(client, extraction):
    _, _, fake_jev = extraction
    fake_jev.other_for = "Sam Nguyen"
    sign_in(client, "staff@example.com.au")
    share(client, "other.md", LEASE)
    drain()
    with SessionLocal() as db:
        rel = db.scalars(select(OntologyCandidate).where(OntologyCandidate.kind == "relation")).all()
        assert rel and all(c.domain_iri and c.range_iri for c in rel)


def test_chunks_are_tagged_with_concepts(client, extraction):
    sign_in(client, "staff@example.com.au")
    aid = share(client, "tags.md", "# Leases\n\nThis is a gross lease for the building.\n")
    drain()
    with SessionLocal() as db:
        doc = db.scalar(select(Document).where(Document.source_id == aid))
        tags = db.scalars(select(ChunkTag).where(ChunkTag.document_id == doc.id)).all()
    o = load()
    assert any(o.label(t.concept_iri) == "Gross lease" for t in tags)


def test_unsafe_graph_names_are_refused():
    with pytest.raises(graph.GraphError):
        graph.local_name("pbo:Bad Label} DETACH DELETE n //")
