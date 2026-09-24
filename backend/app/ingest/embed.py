"""Client for the embedding sidecar (rdb420/embedding-sidecar): dense (MiniLM), sparse (SPLADE) and
ColBERT late-interaction vectors for each chunk, and the query-side versions for search."""
from dataclasses import dataclass

from .. import httpclient, jobs
from ..config import get_settings

BATCH = 32  # the sidecar accepts up to 64 texts a call


class EmbedError(RuntimeError):
    pass


@dataclass
class Vectors:
    dense: list[float]
    sparse: dict  # {"indices": [...], "values": [...]}
    colbert: list[list[float]]


def _post(http, path: str, texts: list[str]) -> list:
    r = http.post(path, json={"texts": texts})
    if r.status_code != 200:
        raise EmbedError(f"The embedding service returned {r.status_code} for {path}.")
    return r.json()["vectors"]


def _client():
    s = get_settings()
    if not s.embed_url:
        raise EmbedError("GW_EMBED_URL is not set.")
    return httpclient.client("embed", base_url=s.embed_url.rstrip("/"), timeout=300)


def embed_documents(texts: list[str]) -> list[Vectors]:
    out: list[Vectors] = []
    with _client() as http:
        for i in range(0, len(texts), BATCH):
            batch = texts[i:i + BATCH]
            dense = _post(http, "/embed/dense", batch)
            sparse = _post(http, "/embed/sparse", batch)
            colbert = _post(http, "/embed/colbert", batch)
            out += [Vectors(d, s, c) for d, s, c in zip(dense, sparse, colbert, strict=True)]
            jobs.heartbeat()
    return out


def embed_query(text: str) -> Vectors:
    with _client() as http:
        return Vectors(_post(http, "/embed/dense", [text])[0], _post(http, "/embed/sparse/query", [text])[0],
                       _post(http, "/embed/colbert/query", [text])[0])
