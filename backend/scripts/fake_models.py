"""Scripted stand-ins for the decision model and the reviewer, for trying the interface without
API keys. Answers come from keyword rules, not a model, so labels and choices will be crude.

    uvicorn scripts.fake_models:app --port 8095      (from backend/)

Then run the API with:
    GW_DECISION_PROVIDER=jev GW_DECISION_URL=http://localhost:8095/v1/systemone
    GW_AI_PROVIDER=openai GW_OPENAI_URL=http://localhost:8095/v1/chat/completions GW_OPENAI_MODEL=fake
"""
import json
import re

from fastapi import FastAPI, Request

app = FastAPI()
CONTEXT = {"issue", "workaround", "external_party", "risk"}

@app.post("/v1/systemone")
async def s1(req: Request):
    b = await req.json(); st = b["state"]; text = st["latest"].lower(); q = b["questions"]
    kind = ("issue" if "because" in text or "wrong" in text or "behind" in text else
            "workaround" if "spreadsheet" in text else "start" if "starts" in text else
            "end" if "closed" in text else "task")
    outside = "tenant" in text or "bank sends" in text
    spans = {k: v for k, v in q["label"]["criteria"].items() if k != "none"}
    actor = next((k for k, v in spans.items() if "tenant" in v.lower() or "bank" in v.lower()), "none")
    targets = [k for k in q["target"]["criteria"] if k != "none"]
    issue_target = next((e["ref"] for e in st["map"]["elements"] if e["kind"] == "issue"), None)
    target = issue_target if "because" in text and issue_target else (targets[0] if targets else "none")
    nouls = {"issue": 0.9 if kind == "issue" else 0.1, "workaround": 0.9 if "spreadsheet" in text else 0.1,
             "states_rule": 0.9 if "week late" in text or "approve" in text else 0.1,
             "from_outside": 0.9 if outside else 0.1, "is_cause": 0.9 if "because" in text else 0.1,
             "exception": 0.1, "compound": 0.1, "directed": 0.1}
    choice = {"action": "add", "group": "context" if kind in CONTEXT else "step",
              "flow_kind": kind if kind in q["flow_kind"]["criteria"] else "task", "context_kind": kind if kind in CONTEXT else "issue",
              "target": target, "other": "none", "update_what": "none", "who": "outside_party" if outside else "not_stated",
              "label": next(iter(spans), "none"), "actor": actor}
    a = {}
    for k, v in q.items():
        a[k] = {"type": "noul", "noul": nouls.get(k, 0.1)} if v["type"] == "noul" else {"type": "choice", "choice": choice[k], "confidence": 0.9}
    return {"model": "fake-jev", "answers": a}

@app.post("/v1/chat/completions")
async def chat(req: Request):
    user = (await req.json())["messages"][1]["content"]
    ids = [l.split(" | ")[0][2:] for l in user.split("\n") if l.startswith("- ") and " | " in l]
    task = next((l.split(" | ")[0][2:] for l in user.split("\n") if "| Task |" in l), ids[0] if ids else "")
    parked = re.findall(r"^- (\w{32}) \[rule\]", user, re.M)
    out = {"summary": "Added the breach-notice rule step and drafted its rule table.",
           "changes": [{"op": "add", "ref": "r1", "kind": "rule_task", "label": "Decide whether to issue breach notice", "after": task, "reason": "Conditions were described", "evidence": "more than a week late"}],
           "rules": [{"name": "Breach notice", "question": "Issue a breach notice?", "element_id": "r1", "inputs": ["Days late", "On payment plan"], "output": "Action",
                      "rows": [{"when": {"Days late": "more than a week", "On payment plan": "no"}, "then": "Issue notice, Dean approves", "source": "more than a week late"},
                               {"when": {"Days late": "more than a week", "On payment plan": "yes"}, "then": "Call tenant", "source": ""}]}],
           "parking_done": parked, "document": "# Rent collection\n\n1. Check bank feed.\n2. Decide whether to issue a breach notice. [TO CONFIRM: exact days]", "open_questions": ["Exact number of days?"]}
    return {"choices": [{"message": {"content": json.dumps(out)}}]}
