"""Qdrant over its REST API (rdb420/rba420-qdrant, TLS on, API key required in deployment).

One collection holds every chunk with three named vectors:
- dense   384-d MiniLM, cosine, HNSW-indexed for first-stage search
- splade  sparse SPLADE (already weighted, so no IDF modifier), for keyword-like matches
- colbert 128-d per-token multivector with MaxSim, not indexed (m=0): only used to rerank

The physical collection is versioned (gw_chunks_v1) behind an alias (gw_chunks), so a new layout
can be built alongside and switched over. Point ids are uuid5 of source and chunk position, so
re-indexing overwrites in place."""
import uuid

from .. import httpclient
from ..config import get_settings

NAMESPACE = uuid.UUID("6f1c2d3e-8a4b-5c6d-9e0f-a1b2c3d4e5f6")
LAYOUT_VERSION = 1
KEYWORD = ["source_type", "source_id", "document_id", "artifact_id", "recording_id", "board_id", "process_ids",
           "layer", "file_kind", "chunk_kind", "uploaded_by", "heading_path"]
INTEGER = ["chunk_index", "page"]
BOOL = ["personal_info"]


class QdrantError(RuntimeError):
    pass


def point_id(source_type: str, source_id: str, idx: int) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{source_type}:{source_id}:{idx}"))


def _client():
    s = get_settings()
    if not s.qdrant_url:
        raise QdrantError("GW_QDRANT_URL is not set.")
    headers = {"api-key": s.qdrant_api_key} if s.qdrant_api_key else {}
    return httpclient.client("qdrant", base_url=s.qdrant_url.rstrip("/"), timeout=120, headers=headers,
                             verify=httpclient.verify_option(s.qdrant_ca_file))


def _check(r, what: str):
    if r.status_code >= 300:
        raise QdrantError(f"Qdrant returned {r.status_code} when {what}.")
    return r.json() if r.content else {}


def alias() -> str:
    return get_settings().qdrant_collection


def ensure_collection(dense_size: int) -> None:
    name = f"{alias()}_v{LAYOUT_VERSION}"
    with _client() as http:
        if http.get(f"/collections/{alias()}").status_code == 200:
            return
        if http.get(f"/collections/{name}").status_code == 404:
            _check(http.put(f"/collections/{name}", json={
                "vectors": {
                    "dense": {"size": dense_size, "distance": "Cosine"},
                    "colbert": {"size": 128, "distance": "Cosine", "multivector_config": {"comparator": "max_sim"},
                                "hnsw_config": {"m": 0}},
                },
                "sparse_vectors": {"splade": {}},
                "on_disk_payload": True,
            }), "creating the collection")
            for field in KEYWORD:
                _check(http.put(f"/collections/{name}/index", json={"field_name": field, "field_schema": "keyword"}),
                       "indexing a field")
            for field in INTEGER:
                _check(http.put(f"/collections/{name}/index", json={"field_name": field, "field_schema": "integer"}),
                       "indexing a field")
            for field in BOOL:
                _check(http.put(f"/collections/{name}/index", json={"field_name": field, "field_schema": "bool"}),
                       "indexing a field")
            _check(http.put(f"/collections/{name}/index", json={
                "field_name": "text", "field_schema": {"type": "text", "tokenizer": "word", "lowercase": True}}),
                "indexing the text")
        _check(http.post("/collections/aliases", json={"actions": [
            {"create_alias": {"collection_name": name, "alias_name": alias()}}]}), "naming the collection")


def upsert(points: list[dict]) -> None:
    with _client() as http:
        for i in range(0, len(points), 64):
            _check(http.put(f"/collections/{alias()}/points", params={"wait": "true"},
                            json={"points": points[i:i + 64]}), "saving chunks")


def _source_filter(source_type: str | None, source_id: str) -> list[dict]:
    must = [{"key": "source_id", "match": {"value": source_id}}]
    if source_type:
        must.append({"key": "source_type", "match": {"value": source_type}})
    return must


def delete_from(source_type: str | None, source_id: str, first_index: int = 0) -> None:
    """Remove a source's chunks at or after first_index (all of them by default)."""
    must = _source_filter(source_type, source_id)
    if first_index:
        must.append({"key": "chunk_index", "range": {"gte": first_index}})
    with _client() as http:
        r = http.post(f"/collections/{alias()}/points/delete", params={"wait": "true"}, json={"filter": {"must": must}})
        if r.status_code == 404:  # no collection yet, so nothing to delete
            return
        _check(r, "removing chunks")


def query(dense: list[float], sparse: dict, colbert: list[list[float]], flt: dict | None, limit: int,
          candidates: int = 50) -> list[dict]:
    """Dense and sparse candidates, reranked together by ColBERT MaxSim."""
    prefetch = [{"query": dense, "using": "dense", "limit": candidates},
                {"query": sparse, "using": "splade", "limit": candidates}]
    if flt:
        for p in prefetch:
            p["filter"] = flt
    body = {"prefetch": prefetch, "query": colbert, "using": "colbert", "limit": limit, "with_payload": True}
    with _client() as http:
        return _check(http.post(f"/collections/{alias()}/points/query", json=body), "searching")["result"]["points"]
