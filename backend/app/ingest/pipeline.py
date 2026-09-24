"""The ingestion pipeline's stages, each a job kind on the existing queue (app/worker.py):

    convert_artifact     file -> blocks + Markdown (MinerU, Gotenberg, native readers)
    transcribe_artifact  audio or video file -> transcript blocks (Parakeet)
    ingest_recording     an ended recording's transcript -> blocks
    index_chunks         blocks -> chunks -> three embeddings -> Qdrant
    extract_entities     chunks -> ontology-typed mentions and relations (GLiNER + Jev)
    project_graph        mentions and relations -> Neo4j
    purge_external       remove a withdrawn or purged source from Qdrant, Neo4j and storage

SQL (documents, chunks, mentions, relations) is the source of truth; Qdrant and Neo4j are built
from it and can be rebuilt with "reprocess". Each stage is idempotent: it skips work whose
inputs haven't changed. Stages never log file content.
"""
import hashlib
import json
import logging

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session as DB

from .. import jobs
from ..config import get_settings
from ..models import Artifact, Board, Chunk, Document, Recording
from ..storage import get_storage, prefix_of
from . import blocks as B
from . import chunker, embed, qdrant
from .convert import AUDIO_VIDEO, Converted, convert

log = logging.getLogger("groundwork.pipeline")
PIPELINE_VERSION = "1"
IDLE = {"withdrawn", "purged", "quarantined", "failed"}


def personal(a: Artifact) -> bool:
    """Yes or not sure both count as personal information."""
    return (a.personal_info or "unsure") != "no"


def start(db: DB, a: Artifact) -> None:
    """Called when a file's first read has finished and the malware check passed."""
    a.pipeline_status = "queued"
    jobs.enqueue(db, "convert_artifact", a.id)


def current_document(db: DB, source_type: str, source_id: str) -> Document | None:
    return db.scalar(select(Document).where(Document.source_type == source_type, Document.source_id == source_id,
                                            Document.is_current.is_(True)).order_by(Document.created_at.desc()))


def _next_version(db: DB, source_type: str, source_id: str) -> int:
    n = db.scalar(select(func.count()).select_from(Document).where(Document.source_type == source_type,
                                                                  Document.source_id == source_id))
    return (n or 0) + 1


def save_document(db: DB, *, source_type: str, source_id: str, prefix: str, sha256: str, result: Converted,
                  personal_info: bool) -> Document:
    """Store the Markdown, blocks, MinerU output and images, and record a new current document."""
    storage = get_storage()
    version = _next_version(db, source_type, source_id)
    folder = f"{prefix}v{version}/"
    markdown = result.markdown or B.to_markdown(result.blocks)
    storage.put_bytes(folder + "document.md", markdown.encode(), "text/markdown; charset=utf-8")
    storage.put_bytes(folder + "blocks.json", json.dumps(result.blocks, ensure_ascii=False).encode(), "application/json")
    if result.content_list:
        storage.put_bytes(folder + "mineru_content_list.json", json.dumps(result.content_list).encode(), "application/json")
    for name, data in result.images.items():
        storage.put_bytes(folder + "images/" + name, data, "image/" + (name.rsplit(".", 1)[-1] or "jpeg"))
    db.execute(update(Document).where(Document.source_type == source_type, Document.source_id == source_id)
               .values(is_current=False))
    doc = Document(source_type=source_type, source_id=source_id, source_sha256=sha256, converter=result.converter,
                   pipeline_version=PIPELINE_VERSION, markdown_key=folder + "document.md",
                   content_list_key=folder + "blocks.json", markdown_sha256=hashlib.sha256(markdown.encode()).hexdigest(),
                   personal_info=personal_info, stage="converted", status="ok", note=result.note[:1000])
    db.add(doc)
    db.flush()
    return doc


def load_blocks(doc: Document) -> list[dict]:
    return json.loads(get_storage().read_bytes(doc.content_list_key))


def after_convert(db: DB, doc: Document) -> str:
    """Queue the next stage, or finish if indexing isn't set up. Returns the artifact status to show."""
    if get_settings().embed_url:
        jobs.enqueue(db, "index_chunks", doc.id)
        return "indexing"
    return "done"


# ---- Stages -----------------------------------------------------------------------------

def convert_artifact(db: DB, aid: str) -> None:
    a = db.get(Artifact, aid)
    if not a or a.status in IDLE or a.scan == "infected" or not a.storage_key:
        return
    ext = "." + a.storage_key.rsplit(".", 1)[-1].lower()
    if ext in AUDIO_VIDEO:
        a.pipeline_status = "queued"
        jobs.enqueue(db, "transcribe_artifact", a.id)
        return
    existing = current_document(db, "artifact", a.id)
    if existing and existing.source_sha256 == a.sha256 and existing.pipeline_version == PIPELINE_VERSION \
            and existing.status == "ok":
        a.pipeline_status = after_convert(db, existing)  # already converted this exact file
        return
    a.pipeline_status = "converting"
    db.commit()
    with get_storage().local_copy(a.storage_key) as path:
        result = convert(path)
    if result.skipped:
        a.pipeline_status = "skipped"
        db.add(Document(source_type="artifact", source_id=a.id, source_sha256=a.sha256, converter=result.converter,
                        pipeline_version=PIPELINE_VERSION, personal_info=personal(a), stage="converted",
                        status="skipped", note=result.note[:1000]))
        return
    doc = save_document(db, source_type="artifact", source_id=a.id, prefix=prefix_of(a.storage_key),
                        sha256=a.sha256, result=result, personal_info=personal(a))
    a.pipeline_status = after_convert(db, doc)
    log.info("converted artifact %s with %s: %d blocks", a.id, result.converter, len(result.blocks))


def after_segment(db: DB, seg) -> None:
    """Called when a recording part has been transcribed. Recordings join the pipeline in phase 3."""


CHUNKER_VERSION = "1"


def source_context(db: DB, doc: Document) -> tuple[str, dict]:
    """The title to use in breadcrumbs and the payload every chunk of this source carries."""
    if doc.source_type == "artifact":
        a = db.get(Artifact, doc.source_id)
        if a is None:
            return "", {}
        return a.title, {"artifact_id": a.id, "uploaded_by": a.uploaded_by, "layer": a.layer, "file_kind": a.kind,
                         "process_ids": [p.id for p in a.processes], "title": a.title}
    rec = db.get(Recording, doc.source_id)
    board = db.get(Board, rec.board_id) if rec else None
    if rec is None or board is None:
        return "", {}
    return f"Session: {board.title}", {"recording_id": rec.id, "board_id": board.id, "uploaded_by": rec.started_by,
                                       "process_ids": [board.process_id] if board.process_id else [],
                                       "title": board.title, "file_kind": "recording", "layer": "actual"}


def _set_status(db: DB, doc: Document, status: str) -> None:
    if doc.source_type == "artifact":
        a = db.get(Artifact, doc.source_id)
        if a:
            a.pipeline_status = status


def after_index(db: DB, doc: Document) -> str:
    if get_settings().extract_url:
        jobs.enqueue(db, "extract_entities", doc.id)
        return "extracting"
    return "done"


def index_chunks(db: DB, doc_id: str) -> None:
    doc = db.get(Document, doc_id)
    if not doc or not doc.is_current or doc.status != "ok":
        return
    s = get_settings()
    key = hashlib.sha256(f"{doc.markdown_sha256}:{CHUNKER_VERSION}:{s.chunk_tokens}:{qdrant.LAYOUT_VERSION}"
                         .encode()).hexdigest()
    if doc.index_key == key and doc.stage != "converted":
        _set_status(db, doc, after_index(db, doc))  # nothing changed since the last index
        return
    title, payload = source_context(db, doc)
    if not payload:
        return
    pieces = chunker.chunk(load_blocks(doc), title, s.chunk_tokens)
    # Embed before touching the database: embedding is slow, and SQLite allows one writer at a time.
    vectors = embed.embed_documents([p.embed_text for p in pieces]) if pieces else []
    db.execute(delete(Chunk).where(Chunk.source_type == doc.source_type, Chunk.source_id == doc.source_id))
    rows = [Chunk(id=qdrant.point_id(doc.source_type, doc.source_id, i), document_id=doc.id,
                  source_type=doc.source_type, source_id=doc.source_id, idx=i, text=p.text,
                  heading_path=p.heading_path, page=p.page, page_end=p.page_end, start_s=p.start_s, end_s=p.end_s,
                  kind=p.kind, tokens=p.tokens) for i, p in enumerate(pieces)]
    db.add_all(rows)
    if pieces:
        qdrant.ensure_collection(len(vectors[0].dense))
        base = payload | {"source_type": doc.source_type, "source_id": doc.source_id, "document_id": doc.id,
                          "personal_info": doc.personal_info}
        qdrant.upsert([{"id": r.id, "vector": {"dense": v.dense, "splade": v.sparse, "colbert": v.colbert},
                        "payload": base | {"chunk_index": r.idx, "chunk_kind": r.kind, "text": r.text,
                                           "heading_path": r.heading_path or [], "page": r.page, "page_end": r.page_end,
                                           "start_s": r.start_s, "end_s": r.end_s}}
                       for r, v in zip(rows, vectors, strict=True)])
    qdrant.delete_from(doc.source_type, doc.source_id, len(pieces))
    doc.chunk_count, doc.index_key, doc.stage = len(pieces), key, "indexed"
    _set_status(db, doc, after_index(db, doc))
    log.info("indexed %s %s: %d chunks", doc.source_type, doc.source_id, len(pieces))


def failed(db: DB, kind: str, ref_id: str) -> None:
    """The worker calls this when a stage has used up its tries."""
    if kind in ("convert_artifact", "transcribe_artifact"):
        a = db.get(Artifact, ref_id)
        if a:
            a.pipeline_status = "failed"
    else:
        doc = db.get(Document, ref_id)
        if doc:
            doc.status = "failed"
            if doc.source_type == "artifact":
                a = db.get(Artifact, doc.source_id)
                if a:
                    a.pipeline_status = "failed"


STAGES = {"convert_artifact": convert_artifact, "index_chunks": index_chunks}
