"""Removing a source from everything the pipeline built from it.

- forget(db, source_id): the SQL records (documents, and through them chunks, mentions,
  relationships, tags and topic links), and the source's evidence on open ontology proposals
  (a proposal left with no evidence goes too). Runs inside the purge.
- purge_external: a job that removes the source's points from Qdrant, its part of the Neo4j graph,
  and retries the stored files if the purge couldn't delete them. Retried with backoff like every
  job, so a service that is down doesn't leave anything behind.
"""
import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DB

from .. import audit, jobs
from ..config import get_settings
from ..models import Artifact, Chunk, Document, OntologyCandidate
from ..storage import get_storage, prefix_of
from ..util import deleted

log = logging.getLogger("groundwork.pipeline")


def forget(db: DB, source_id: str) -> int:
    chunk_ids = set(db.scalars(select(Chunk.id).where(Chunk.source_id == source_id)).all())
    if chunk_ids:
        for c in db.scalars(select(OntologyCandidate).where(OntologyCandidate.status == "open")).all():
            kept = [x for x in (c.evidence or []) if x not in chunk_ids]
            if len(kept) != len(c.evidence or []):
                if kept:
                    c.evidence = kept
                else:
                    db.delete(c)
    return deleted(db, delete(Document).where(Document.source_id == source_id))


def schedule(db: DB, source_id: str) -> None:
    """Queue removal from the external stores, if the pipeline has ever been set up."""
    s = get_settings()
    if s.qdrant_url or s.neo4j_url or s.storage_backend == "s3":
        jobs.enqueue(db, "purge_external", source_id)


def purge_external(db: DB, source_id: str) -> None:
    from . import graph, qdrant
    s = get_settings()
    done: dict[str, object] = {}
    if s.qdrant_url:
        qdrant.delete_from(None, source_id)
        done["qdrant"] = True
    if s.neo4j_url:
        graph.remove_source(source_id)
        done["graph"] = True
    a = db.get(Artifact, source_id)
    if a is not None and a.status == "purged" and a.storage_key:  # the purge couldn't delete the files
        done["files"] = get_storage().delete_prefix(prefix_of(a.storage_key))
        a.storage_key = ""
    audit.record(db, "artifact.purge_cascaded" if a is not None and a.status == "purged" else "source.unindexed",
                 "artifact" if a is not None else "recording", source_id, actor_type="system", detail=done)
    log.info("removed %s from %s", source_id, ", ".join(done) or "nothing")
