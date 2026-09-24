"""The knowledge graph in Neo4j, built from the SQL extraction records over Neo4j's Query API
(POST /db/{database}/query/v2), with plain httpx like every other client here.

    (:OntClass)-[:SUBCLASS_OF]->(:OntClass)      the pinned ontology, loaded once per version
    (:OntProperty), (:Concept {scheme})          its properties and SKOS concepts (roles included)
    (:Source)-[:HAS_CHUNK]->(:Chunk)             provenance; no chunk text is copied into the graph
    (:Entity:<Class>)-[:MENTIONED_IN]->(:Chunk)  things found in the text, joined by entity key
    (:Entity)-[:INSTANCE_OF]->(:OntClass)
    (:Entity)-[:<property>]->(:Entity)           relationships, each with sources[], confidence,
                                                 model, status "draft" and the ontology version
    (ctx)-[:hasParticipation]->(:Entity:Participation)-[:participant]->(party), -[:inRole]->(:Concept)
    (:Chunk)-[:TAGGED]->(:Concept)

Labels and relationship types can't be query parameters, so they are checked against the ontology
and a strict pattern before they are written into a statement. Everything else is a parameter.
"""
import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from .. import httpclient, jobs
from ..config import get_settings
from ..models import Artifact, Board, Chunk, ChunkTag, Document, EntityMention, Recording, RelationAssertion
from .ontology import Ontology, load

NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,80}$")
NAMESPACE = uuid.UUID("5d0c8e1f-2a3b-5c4d-8e9f-0a1b2c3d4e5f")
BATCH = 500
_loaded: set[str] = set()


class GraphError(RuntimeError):
    pass


def local_name(iri: str) -> str:
    name = iri.split(":", 1)[-1].split("#")[-1]
    if not NAME.match(name):
        raise GraphError(f"Refusing an unsafe graph name: {name[:40]!r}")
    return name


def _client():
    s = get_settings()
    if not s.neo4j_url:
        raise GraphError("GW_NEO4J_URL is not set.")
    http = httpclient.client("neo4j", base_url=s.neo4j_url.rstrip("/"), timeout=120)
    http.auth = (s.neo4j_user, s.neo4j_password)
    return http


def run(statements: list[tuple[str, dict]]) -> list[dict]:
    s = get_settings()
    out = []
    with _client() as http:
        for statement, params in statements:
            r = http.post(f"/db/{s.neo4j_database}/query/v2", json={"statement": statement, "parameters": params})
            body = r.json() if r.content else {}
            if r.status_code >= 300 or body.get("errors"):
                code = (body.get("errors") or [{}])[0].get("code", "")
                raise GraphError(f"Neo4j returned {r.status_code} {code}.")
            out.append(body.get("data", {}))
    return out


def _batched(statement: str, rows: list[dict], extra: dict | None = None) -> list[tuple[str, dict]]:
    return [(statement, {"rows": rows[i:i + BATCH], **(extra or {})}) for i in range(0, len(rows), BATCH)]


def ensure_ontology(o: Ontology) -> None:
    if o.version in _loaded:
        return
    found = run([("MATCH (v:OntologyVersion {version: $v}) RETURN count(v) AS n", {"v": o.version})])[0]
    if (found.get("values") or [[0]])[0][0]:
        _loaded.add(o.version)
        return
    classes = [{"iri": i, "label": t.get("label", ""), "definition": t.get("definition", "")} for i, t in o.classes.items()]
    subs = [{"sub": c, "sup": p} for c, ps in o.parents.items() for p in ps]
    props = [{"iri": i, "label": t.get("label", ""), "domain": t.get("domain") or "", "range": t.get("range") or ""}
             for i, t in o.properties.items()]
    concepts = [{"iri": c["iri"], "label": c.get("label", ""), "scheme": s} for s, cs in o.concepts.items() for c in cs]
    stmts: list[tuple[str, dict]] = [
        ("CREATE CONSTRAINT gw_entity_key IF NOT EXISTS FOR (e:Entity) REQUIRE e.key IS UNIQUE", {}),
        ("CREATE CONSTRAINT gw_chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE", {}),
        ("CREATE CONSTRAINT gw_source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.id IS UNIQUE", {}),
        ("CREATE CONSTRAINT gw_class_iri IF NOT EXISTS FOR (c:OntClass) REQUIRE c.iri IS UNIQUE", {}),
        ("CREATE CONSTRAINT gw_concept_iri IF NOT EXISTS FOR (c:Concept) REQUIRE c.iri IS UNIQUE", {}),
    ]
    stmts += _batched("UNWIND $rows AS c MERGE (n:OntClass {iri: c.iri}) SET n.label = c.label, "
                      "n.definition = c.definition", classes)
    stmts += _batched("UNWIND $rows AS s MATCH (a:OntClass {iri: s.sub}), (b:OntClass {iri: s.sup}) "
                      "MERGE (a)-[:SUBCLASS_OF]->(b)", subs)
    stmts += _batched("UNWIND $rows AS p MERGE (n:OntProperty {iri: p.iri}) SET n.label = p.label, "
                      "n.domain = p.domain, n.range = p.range", props)
    stmts += _batched("UNWIND $rows AS c MERGE (n:Concept {iri: c.iri}) SET n.label = c.label, n.scheme = c.scheme",
                      concepts)
    stmts.append(("MERGE (v:OntologyVersion {version: $v}) SET v.ref = $ref", {"v": o.version, "ref": o.ref}))
    run(stmts)
    _loaded.add(o.version)


def remove_source(source_id: str) -> None:
    """Take a source out of the graph: its chunks, its evidence on every relationship (deleting
    relationships left with none), then entities and participations nothing supports any more."""
    run([
        ("MATCH (:Source {id: $id})-[:HAS_CHUNK]->(c:Chunk) WITH collect(c.id) AS ids "
         "MATCH ()-[r]->() WHERE r.sources IS NOT NULL AND any(x IN r.sources WHERE x IN ids) "
         "SET r.sources = [x IN r.sources WHERE NOT x IN ids] "
         "WITH r WHERE size(r.sources) = 0 DELETE r", {"id": source_id}),
        ("MATCH (s:Source {id: $id}) OPTIONAL MATCH (s)-[:HAS_CHUNK]->(c:Chunk) DETACH DELETE c, s", {"id": source_id}),
        ("MATCH (p:Participation) WHERE NOT (p)-[:participant]->() DETACH DELETE p", {}),
        ("MATCH (e:Entity) WHERE NOT e:Participation AND NOT (e)-[:MENTIONED_IN]->() DETACH DELETE e", {}),
    ])


_EDGE = ("ON CREATE SET x.sources = [r.chunk], x.confidence = r.conf, x.model = r.model, x.status = 'draft', "
         "x.ontology_version = $v "
         "ON MATCH SET x.sources = CASE WHEN r.chunk IN x.sources THEN x.sources ELSE x.sources + r.chunk END, "
         "x.confidence = CASE WHEN r.conf > x.confidence THEN r.conf ELSE x.confidence END")


def _title(db: DB, doc: Document) -> str:
    if doc.source_type == "artifact":
        a = db.get(Artifact, doc.source_id)
        return a.title if a else ""
    rec = db.get(Recording, doc.source_id)
    board = db.get(Board, rec.board_id) if rec else None
    return f"Session: {board.title}" if board else "Session"


def project(db: DB, doc: Document) -> dict:
    """Replace this source's part of the graph with what SQL holds now."""
    o = load()
    ensure_ontology(o)
    remove_source(doc.source_id)
    chunks = db.scalars(select(Chunk).where(Chunk.document_id == doc.id)).all()
    mentions = db.scalars(select(EntityMention).where(EntityMention.document_id == doc.id,
                                                     EntityMention.status != "rejected")).all()
    relations = db.scalars(select(RelationAssertion).where(RelationAssertion.document_id == doc.id,
                                                          RelationAssertion.status != "rejected")).all()
    tags = db.scalars(select(ChunkTag).where(ChunkTag.document_id == doc.id)).all()
    by_id = {m.id: m for m in mentions}
    v = o.version
    stmts = [("MERGE (s:Source {id: $id}) SET s.type = $type, s.title = $title, s.personal_info = $pi, "
              "s.document_id = $doc", {"id": doc.source_id, "type": doc.source_type, "title": _title(db, doc),
                                       "pi": doc.personal_info, "doc": doc.id})]
    stmts += _batched("MATCH (s:Source {id: $id}) UNWIND $rows AS c MERGE (k:Chunk {id: c.id}) "
                      "SET k.idx = c.idx, k.page = c.page, k.start_s = c.start_s MERGE (s)-[:HAS_CHUNK]->(k)",
                      [{"id": c.id, "idx": c.idx, "page": c.page, "start_s": c.start_s} for c in chunks],
                      {"id": doc.source_id})
    by_class: dict[str, list[dict]] = {}
    for m in mentions:
        if m.class_iri not in o.classes:
            continue
        by_class.setdefault(m.class_iri, []).append({"key": m.entity_key, "name": m.surface, "chunk": m.chunk_id,
                                                     "start": m.start, "end": m.end, "iri": m.class_iri})
    for iri, rows in by_class.items():
        label = local_name(iri)
        stmts += _batched(
            f"UNWIND $rows AS m MATCH (k:Chunk {{id: m.chunk}}) MATCH (c:OntClass {{iri: m.iri}}) "
            f"MERGE (e:Entity {{key: m.key}}) ON CREATE SET e.name = m.name, e.class_iri = m.iri "
            f"SET e:{label}, e.personal_info = coalesce(e.personal_info, false) OR $pi "
            f"MERGE (e)-[t:MENTIONED_IN {{start: m.start}}]->(k) SET t.end = m.end "
            f"MERGE (e)-[:INSTANCE_OF]->(c)", rows, {"pi": doc.personal_info})
    stmts += _batched("UNWIND $rows AS t MATCH (k:Chunk {id: t.chunk}), (c:Concept {iri: t.iri}) "
                      "MERGE (k)-[x:TAGGED]->(c) SET x.confidence = t.conf",
                      [{"chunk": t.chunk_id, "iri": t.concept_iri, "conf": t.confidence} for t in tags])
    direct: dict[str, list[dict]] = {}
    roles: list[dict] = []
    for r in relations:
        a, b = by_id.get(r.subject_mention_id), by_id.get(r.object_mention_id)
        if not a or not b:
            continue
        row = {"a": a.entity_key, "b": b.entity_key, "chunk": r.chunk_id, "conf": r.confidence, "model": r.model}
        if r.property_iri and r.property_iri in o.properties:
            direct.setdefault(r.property_iri, []).append(row)
        elif r.role_iri and r.role_iri in o.roles:
            key = str(uuid.uuid5(NAMESPACE, f"{a.entity_key}|{r.role_iri}|{b.entity_key}"))
            roles.append(row | {"role": r.role_iri, "key": key,
                                "name": f"{a.surface} as {o.label(r.role_iri)} of {b.surface}"})
    for iri, rows in direct.items():
        rel = local_name(iri)
        stmts += _batched(f"UNWIND $rows AS r MATCH (a:Entity {{key: r.a}}), (b:Entity {{key: r.b}}) "
                          f"MERGE (a)-[x:{rel}]->(b) {_EDGE}", rows, {"v": v})
    if roles:
        stmts += _batched(
            "UNWIND $rows AS r MATCH (party:Entity {key: r.a}), (ctx:Entity {key: r.b}), (role:Concept {iri: r.role}) "
            "MERGE (p:Entity:Participation {key: r.key}) ON CREATE SET p.name = r.name, p.class_iri = 'pbo:Participation' "
            f"WITH r, p, party, ctx, role MERGE (ctx)-[x:hasParticipation]->(p) {_EDGE} "
            f"WITH r, p, party, role MERGE (p)-[x:participant]->(party) {_EDGE} "
            f"WITH r, p, role MERGE (p)-[x:inRole]->(role) {_EDGE}", roles, {"v": v})
    run(stmts)
    jobs.heartbeat()
    return {"entities": len({m.entity_key for m in mentions}), "relations": sum(map(len, direct.values())) + len(roles)}
