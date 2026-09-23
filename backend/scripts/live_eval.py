"""Measure the live interpreter against sentences you have labelled by hand.

Record a mock mapping session, write down what should have happened for each sentence, then:

    cd backend
    GW_DECISION_PROVIDER=jev GW_DECISION_API_KEY=... python -m scripts.live_eval scripts/eval/sample.jsonl

Run the same file against hosted Jev and a local Laya or OpenJev server (change GW_DECISION_URL
and GW_DECISION_MODEL) to compare them on your own conversations before trusting either.

Each line: {"text": "...", "expect": {"action": "add", "kind": "workaround"}, "doc": optional canvas,
            "pass": "overview" or "detail" (default detail)}
"""
import json
import statistics
import sys
from pathlib import Path

from app.live import jev
from app.live.interpret import build_request, plan

EMPTY = {"nodes": [], "edges": []}


def main(path: str):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    hits = {"action": 0, "kind": 0}
    kind_total, latencies, recent = 0, [], []
    for r in rows:
        state, questions, ctx = build_request(r["text"], recent, r.get("doc") or EMPTY, None, r.get("pass", "detail"))
        answers, model, ms = jev.system_one(state, questions)
        ops, parking, summary = plan(answers, ctx, "listen", r["text"])
        latencies.append(ms)
        exp = r["expect"]
        ok_action = summary["action"] == exp["action"]
        hits["action"] += ok_action
        if "kind" in exp:
            kind_total += 1
            hits["kind"] += summary["kind"] == exp["kind"]
        mark = "ok " if ok_action and summary["kind"] == exp.get("kind", summary["kind"]) else "MISS"
        print(f"{mark} {r['text'][:60]:<60} got {summary['action']}/{summary['kind']} "
              f"({summary['action_conf']:.2f}) want {exp.get('action')}/{exp.get('kind', '-')} {ms} ms")
        recent = (recent + [r["text"]])[-3:]
    print(f"\nmodel {model}: action {hits['action']}/{len(rows)}, kind {hits['kind']}/{kind_total}, "
          f"median latency {statistics.median(latencies):.0f} ms")


if __name__ == "__main__":
    main(sys.argv[1])
