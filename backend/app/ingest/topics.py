"""Themes across everything indexed, from BERTopic in the extraction sidecar. Fitted on YSH's own
chunks (the published arXiv and Wikipedia topic models don't know property work), guided by seed
words from the ontology's SKOS concepts. A topic that matches a concept is linked to it; one that
matches nothing becomes a proposed category value for an analyst to review."""
import re

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session as DB

from ..config import get_settings
from ..models import Artifact, Chunk, ChunkTopic, Document, Topic
from . import extract, extractor
from .ontology import load

STOP = {"and", "or", "the", "of", "for", "to", "a", "an", "in", "on", "by", "with", "per"}


def _words(label: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", label.lower()) if w not in STOP and len(w) > 2]


def run(db: DB) -> dict:
    s = get_settings()
    o = load()
    chunks = db.scalars(select(Chunk).join(Document, Document.id == Chunk.document_id)
                        .where(Document.is_current.is_(True), Chunk.kind != "image",
                               or_(Document.source_type != "artifact",
                                   Document.source_id.in_(select(Artifact.id).where(
                                       Artifact.status.not_in(("withdrawn", "purged", "quarantined"))))))).all()
    if len(chunks) < s.topics_min_chunks:
        return {"skipped": f"Topics need at least {s.topics_min_chunks} chunks; there are {len(chunks)}."}
    concepts = [c for scheme, cs in o.concepts.items() if scheme != "pbo:RoleScheme" for c in cs]
    seeds = [w for w in (_words(c["label"]) for c in concepts) if w]
    result = extractor.fit_topics([c.text for c in chunks], seeds)
    db.execute(delete(ChunkTopic))
    db.execute(delete(Topic))
    by_number: dict[int, Topic] = {}
    proposed = 0
    for t in result["topics"]:
        if int(t["id"]) < 0:  # BERTopic's outliers
            continue
        words = [str(w) for w in t.get("words", [])][:10]
        top = set(words[:6])
        match = max(concepts, key=lambda c: len(top & set(_words(c["label"]))), default=None)
        concept = match["iri"] if match and len(top & set(_words(match["label"]))) >= min(2, len(_words(match["label"]))) else ""
        topic = Topic(number=int(t["id"]), words=words, size=int(t.get("size", 0)), concept_iri=concept)
        db.add(topic)
        db.flush()
        by_number[topic.number] = topic
        if not concept and words:
            evidence = [chunks[i].id for i in t.get("documents", [])[:5] if 0 <= i < len(chunks)]
            for chunk_id in evidence or [chunks[0].id]:
                extract.propose(db, o, "concept", " ".join(words[:3]), chunk_id)
            proposed += 1
    for i, number in enumerate(result.get("assignments", [])):
        assigned = by_number.get(int(number))
        if assigned and i < len(chunks):
            db.add(ChunkTopic(chunk_id=chunks[i].id, topic_id=assigned.id))
    return {"topics": len(by_number), "proposed": proposed}
