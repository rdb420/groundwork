"""Measure extraction against chunks you have labelled by hand, before switching the pipeline on
for everyone. Uses the extraction sidecar and decision model set in .env.

    cd backend && uv run python -m scripts.extract_eval scripts/eval/extract_sample.jsonl

Each line: {"text": "...",
            "entities": [{"text": "Sam Nguyen", "class": "pbo:Person"}, ...],
            "relations": [{"a": "Sam Nguyen", "b": "residential tenancy agreement", "role": "pbo:Role_Tenant"},
                          {"a": "...", "b": "...", "property": "pbo:managedBy"}]}

Reports entity precision and recall (by text and class), relation precision and recall, and how
many chunks produced ontology proposals. Use sentences from real (non-personal) YSH documents.
"""
import json
import sys
from pathlib import Path

from app.ingest import extract
from app.ingest.ontology import load


def main(path: str) -> None:
    o = load()
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    texts = [r["text"] for r in rows]
    mentions = extract.find_mentions(o, texts, 0.5)
    extract.confirm_classes(o, mentions, texts, None)
    relations, _ = extract.find_relations(o, mentions, texts, None, 12, 0.5)
    ent = {"tp": 0, "fp": 0, "fn": 0}
    rel = {"tp": 0, "fp": 0, "fn": 0}
    for i, r in enumerate(rows):
        got = {(m.text.casefold(), m.class_iri) for m in mentions if m.chunk == i and m.class_iri}
        want = {(e["text"].casefold(), e["class"]) for e in r.get("entities", [])}
        ent["tp"] += len(got & want)
        ent["fp"] += len(got - want)
        ent["fn"] += len(want - got)
        got_r = set()
        for a, b, option, _ in relations:
            if a.chunk != i:
                continue
            s, t = (b, a) if option.reverse else (a, b)
            got_r.add((s.text.casefold(), t.text.casefold(), option.property_iri or option.role_iri))
        want_r = {(x["a"].casefold(), x["b"].casefold(), x.get("property") or x.get("role")) for x in r.get("relations", [])}
        rel["tp"] += len(got_r & want_r)
        rel["fp"] += len(got_r - want_r)
        rel["fn"] += len(want_r - got_r)
        for miss in sorted(want - got):
            print(f"MISS entity {miss} in: {r['text'][:70]}")
    for name, c in (("entities", ent), ("relations", rel)):
        p = c["tp"] / ((c["tp"] + c["fp"]) or 1)
        rc = c["tp"] / ((c["tp"] + c["fn"]) or 1)
        print(f"{name}: precision {p:.2f}, recall {rc:.2f} ({c['tp']} right, {c['fp']} extra, {c['fn']} missed)")
    print(f"catch-all spans (would become proposals): {sum(1 for m in mentions if not m.class_iri)}")


if __name__ == "__main__":
    main(sys.argv[1])
