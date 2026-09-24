"""Measure extraction against chunks you have labelled by hand, before switching the pipeline on
for everyone. Uses the extraction sidecar and decision model set in .env.

    cd backend && uv run python -m scripts.extract_eval scripts/eval/extract_sample.jsonl
    cd backend && uv run python -m scripts.extract_eval --gold-mentions scripts/eval/relations_sample.jsonl

--gold-mentions skips GLiNER2 and asks only the relationship questions about the labelled entities,
so decision models (hosted Jev, a local Laya) can be compared without the extraction sidecar. There,
each relation lists the answers that count as right ("any"); pairs not listed should get "none".

Each line: {"text": "...",
            "entities": [{"text": "Sam Nguyen", "class": "pbo:Person"}, ...],
            "relations": [{"a": "Sam Nguyen", "b": "residential tenancy agreement", "role": "pbo:Role_Tenant"},
                          {"a": "...", "b": "...", "property": "pbo:managedBy"}]}

Reports entity precision and recall (by text and class), relation precision and recall, and how
many chunks produced ontology proposals. Use sentences from real (non-personal) YSH documents.
"""
import json
import sys
import time
from pathlib import Path

from app.ingest import extract
from app.ingest.ontology import load


def gold_relations(path: str) -> None:
    o = load()
    target = extract.extraction_target()
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    texts = [r["text"] for r in rows]
    mentions = []
    for i, r in enumerate(rows):
        for e in r["entities"]:
            start = r["text"].index(e["text"])
            mentions.append(extract.Mention(i, start, start + len(e["text"]), e["text"], e["class"], 1.0))
    t0 = time.perf_counter()
    found, other = extract.find_relations(o, mentions, texts, target, 12, 0.0)
    seconds = time.perf_counter() - t0
    right = wrong = missed = spurious = 0
    for i, r in enumerate(rows):
        want = {(x["a"], x["b"]): set(x["any"]) for x in r.get("relations", [])}
        got = {}
        for a, b, option, conf in found:
            if a.chunk == i:
                s_, t_ = (b, a) if option.reverse else (a, b)
                got[(s_.text, t_.text)] = (option.property_iri or option.role_iri, conf)
                got[(t_.text, s_.text, "rev")] = got[(s_.text, t_.text)]
        for (a, b), ok in want.items():
            hit = got.get((a, b)) or got.get((b, a, "rev"))
            if hit and hit[0] in ok:
                right += 1
            elif hit:
                wrong += 1
                print(f"WRONG {a} -> {b}: got {hit[0]} ({hit[1]:.2f}), want one of {sorted(ok)}")
            else:
                missed += 1
                print(f"MISS  {a} -> {b}: want one of {sorted(ok)}")
        listed = {frozenset(k) for k in want}
        for k, (iri, conf) in got.items():
            if len(k) == 2 and frozenset(k) not in listed:
                spurious += 1
                print(f"EXTRA {k[0]} -> {k[1]}: {iri} ({conf:.2f}) where the text states none")
    total = right + wrong + missed
    print(f"{target.url if target else 'no target'} model {target.model if target else '-'} ({target.flavour if target else '-'}): "
          f"{right}/{total} right, {wrong} wrong, {missed} missed, {spurious} invented, {len(other)} 'another relationship'; "
          f"{seconds:.1f} s")


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
    if sys.argv[1] == "--gold-mentions":
        gold_relations(sys.argv[2])
    else:
        main(sys.argv[1])
