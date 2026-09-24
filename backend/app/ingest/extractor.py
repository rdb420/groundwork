"""Client for the extraction sidecar (deploy/extraction-sidecar): GLiNER2 entities with character
spans and confidence, GLiNER2 classification for chunk tags, and BERTopic for topics. It runs on
the inference box so Groundwork's own image carries no torch."""
from .. import httpclient, jobs
from ..config import get_settings

BATCH = 16


class ExtractError(RuntimeError):
    pass


def _client(timeout: float = 300):
    s = get_settings()
    if not s.extract_url:
        raise ExtractError("GW_EXTRACT_URL is not set.")
    return httpclient.client("extract", base_url=s.extract_url.rstrip("/"), timeout=timeout)


def _post(http, path: str, body: dict) -> dict:
    r = http.post(path, json=body)
    if r.status_code != 200:
        raise ExtractError(f"The extraction service returned {r.status_code} for {path}.")
    return r.json()


def entities(texts: list[str], labels: dict[str, str], threshold: float) -> list[list[dict]]:
    """For each text: [{"label", "text", "start", "end", "confidence"}, ...]."""
    out: list[list[dict]] = []
    with _client() as http:
        for i in range(0, len(texts), BATCH):
            out += _post(http, "/entities", {"texts": texts[i:i + BATCH], "labels": labels,
                                             "threshold": threshold})["results"]
            jobs.heartbeat()
    return out


def classify(texts: list[str], tasks: dict[str, list[str]], threshold: float) -> list[dict[str, list[dict]]]:
    """For each text: {task: [{"label", "confidence"}, ...]} (multi-label)."""
    out: list[dict] = []
    with _client() as http:
        for i in range(0, len(texts), BATCH):
            out += _post(http, "/classify", {"texts": texts[i:i + BATCH], "tasks": tasks,
                                             "threshold": threshold})["results"]
            jobs.heartbeat()
    return out


def fit_topics(texts: list[str], seeds: list[list[str]]) -> dict:
    with _client(timeout=3600) as http:
        return _post(http, "/topics/fit", {"texts": texts, "seed_topics": seeds})
