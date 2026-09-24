"""Search the indexed chunks: dense and sparse candidates, reranked by ColBERT. Internal for now
(the pipeline-only build); later it feeds AI drafts and a search page.

Access follows the rest of Groundwork: contributors find only their own files (and sessions on
maps, which are shared); analysts and admins find everything. Withdrawn and deleted files never
come back, even if Qdrant hasn't caught up yet."""
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from ..models import Artifact, User
from ..security import can_see_all
from . import embed, qdrant


def search(db: DB, user: User, q: str, k: int = 10, process_id: str | None = None) -> list[dict]:
    q = " ".join(q.split())[:2000]
    if not q:
        return []
    must: list[dict] = []
    if process_id:
        must.append({"key": "process_ids", "match": {"value": process_id}})
    flt: dict = {"must": must} if must else {}
    if not can_see_all(user):
        flt["should"] = [{"key": "uploaded_by", "match": {"value": user.id}},
                         {"key": "source_type", "match": {"value": "recording"}}]
    v = embed.embed_query(q)
    hits = qdrant.query(v.dense, v.sparse, v.colbert, flt or None, k * 2)
    artifact_ids = {h["payload"].get("artifact_id") for h in hits if h["payload"].get("artifact_id")}
    live = set(db.scalars(select(Artifact.id).where(Artifact.id.in_(artifact_ids),
                                                    Artifact.status.not_in(("withdrawn", "purged", "quarantined"))))
               ) if artifact_ids else set()
    out = []
    for h in hits:
        p = h["payload"]
        if p.get("artifact_id") and p["artifact_id"] not in live:
            continue
        out.append({"score": h.get("score"), "text": p.get("text", ""), "title": p.get("title", ""),
                    "heading_path": p.get("heading_path", []), "page": p.get("page"), "start_s": p.get("start_s"),
                    "artifact_id": p.get("artifact_id"), "recording_id": p.get("recording_id"),
                    "board_id": p.get("board_id"), "chunk_index": p.get("chunk_index")})
        if len(out) == k:
            break
    return out
