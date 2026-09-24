"""Groundwork's extraction sidecar: GLiNER2 for entities and chunk tags, BERTopic for themes.
Runs on the inference box (CPU works; the RTX 3090 is faster) so Groundwork's own image carries no
torch. Keep it on the private network: it has no authentication, like the embedding sidecar.

    POST /entities   {"texts": [...], "labels": {label: description}, "threshold": 0.5}
                     -> {"results": [[{"label", "text", "start", "end", "confidence"}, ...], ...]}
    POST /classify   {"texts": [...], "tasks": {task: [labels]}, "threshold": 0.5}
                     -> {"results": [{task: [{"label", "confidence"}, ...]}, ...]}   (multi-label)
    POST /topics/fit {"texts": [...], "seed_topics": [[words], ...]}
                     -> {"topics": [{"id", "words", "size", "documents"}], "assignments": [topic id per text]}
    GET  /health

It never logs the texts it receives.
"""
import logging
import os
import time
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

MODEL = os.environ.get("GLINER2_MODEL", "fastino/gliner2-large-v1")
DEVICE = os.environ.get("DEVICE", "cuda")
TOPIC_EMBEDDER = os.environ.get("TOPIC_EMBEDDER", "sentence-transformers/all-MiniLM-L6-v2")
MAX_TEXTS = int(os.environ.get("MAX_TEXTS", "64"))
BATCH = int(os.environ.get("BATCH", "8"))

log = logging.getLogger("extraction-sidecar")
app = FastAPI(title="Groundwork extraction sidecar")
started = time.time()


@lru_cache
def gliner():
    import torch
    from gliner2 import GLiNER2
    device = DEVICE if DEVICE != "cuda" or torch.cuda.is_available() else "cpu"
    model = GLiNER2.from_pretrained(MODEL)
    return model.to(device) if hasattr(model, "to") else model


class EntitiesIn(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=MAX_TEXTS)
    labels: dict[str, str] = Field(min_length=1, max_length=50)
    threshold: float = 0.5


class ClassifyIn(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=MAX_TEXTS)
    tasks: dict[str, list[str]] = Field(min_length=1)
    threshold: float = 0.5


class TopicsIn(BaseModel):
    texts: list[str] = Field(min_length=10, max_length=200_000)
    seed_topics: list[list[str]] = []


def _spans(found: dict, threshold: float) -> list[dict]:
    """GLiNER2's {'entities': {label: [{'text', 'confidence', 'start', 'end'}]}} flattened."""
    out = []
    for label, items in (found.get("entities") or {}).items():
        for it in items or []:
            if isinstance(it, str):  # without spans; can't be placed in the text
                continue
            conf = float(it.get("confidence", 1.0))
            if conf >= threshold and it.get("start") is not None:
                out.append({"label": label, "text": it.get("text", ""), "start": int(it["start"]),
                            "end": int(it["end"]), "confidence": round(conf, 4)})
    return out


@app.post("/entities")
def entities(body: EntitiesIn):
    model = gliner()
    try:
        results = model.batch_extract_entities(body.texts, body.labels, include_confidence=True, include_spans=True,
                                               batch_size=BATCH, threshold=body.threshold)
    except TypeError:  # versions without a threshold argument: filter afterwards
        results = model.batch_extract_entities(body.texts, body.labels, include_confidence=True, include_spans=True,
                                               batch_size=BATCH)
    return {"results": [_spans(r, body.threshold) for r in results]}


def _labels(value, threshold: float) -> list[dict]:
    """classify_text's answer in any of its shapes, as [{'label', 'confidence'}]."""
    items = value if isinstance(value, list) else [value]
    out = []
    for it in items:
        if isinstance(it, dict):
            conf = float(it.get("confidence", 1.0))
            if conf >= threshold and it.get("label"):
                out.append({"label": it["label"], "confidence": round(conf, 4)})
        elif isinstance(it, str) and it:
            out.append({"label": it, "confidence": 1.0})
    return out


@app.post("/classify")
def classify(body: ClassifyIn):
    model = gliner()
    schema = {task: {"labels": labels, "multi_label": True, "cls_threshold": body.threshold}
              for task, labels in body.tasks.items() if labels}
    results = []
    for text in body.texts:
        found = model.classify_text(text, schema, include_confidence=True)
        results.append({task: _labels(found.get(task), body.threshold) for task in schema})
    return {"results": results}


@app.post("/topics/fit")
def fit_topics(body: TopicsIn):
    from bertopic import BERTopic
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer(TOPIC_EMBEDDER, device=DEVICE if DEVICE == "cpu" else None)
    model = BERTopic(embedding_model=embedder, seed_topic_list=body.seed_topics or None,
                     min_topic_size=max(5, len(body.texts) // 200), calculate_probabilities=False)
    try:
        assignments, _ = model.fit_transform(body.texts)
    except ValueError as e:  # too little text for UMAP/HDBSCAN
        raise HTTPException(422, f"Not enough text to find topics: {type(e).__name__}") from None
    topics = []
    for tid in sorted(set(assignments)):
        words = [w for w, _ in (model.get_topic(tid) or [])][:10]
        docs = [i for i, a in enumerate(assignments) if a == tid]
        topics.append({"id": int(tid), "words": words, "size": len(docs), "documents": docs[:50]})
    return {"topics": topics, "assignments": [int(a) for a in assignments]}


@app.get("/health")
def health():
    return {"ok": True, "model": MODEL, "loaded": gliner.cache_info().currsize > 0,
            "uptime_seconds": round(time.time() - started)}
