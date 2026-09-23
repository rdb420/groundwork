import json

from app.config import get_settings
from app.live import combine as cb
from app.live import review as rv
from app.routers import live as live_router
from tests.conftest import sign_in

H = {"x-requested-with": "groundwork"}

DOC = {"nodes": [
    {"id": "lane-a", "type": "lane", "position": {"x": 0, "y": 0}, "width": 900, "height": 200,
     "data": {"label": "Property manager"}},
    {"id": "s1", "type": "bpmnStart", "position": {"x": 40, "y": 80}, "data": {"label": "Rent due"}},
    {"id": "t1", "type": "bpmnTask", "position": {"x": 160, "y": 70}, "width": 150, "height": 64,
     "data": {"label": "Check bank feed"}},
    {"id": "i1", "type": "issue", "position": {"x": 160, "y": -60}, "data": {"label": "Feed shows unpaid rent"}},
], "edges": [{"id": "e1", "source": "s1", "target": "t1"},
             {"id": "e2", "source": "i1", "target": "t1", "data": {"flow": "association"}}], "viewport": None}


def enable(monkeypatch, **kw):
    s = get_settings()
    for k, v in {"decision_provider": "jev", "decision_is_local": False, **kw}.items():
        monkeypatch.setattr(s, k, v)


def fake_jev(action="add", group="context", flow_kind="task", context_kind="workaround", target="t1", conf=0.9,
             who="not_stated", actor=None, **nouls):
    seen = {}

    def call(state, questions):
        seen["state"], seen["questions"] = state, questions
        spans = [k for k in questions["label"]["criteria"] if k != "none"]
        actors = [k for k in questions["actor"]["criteria"] if k != "none"]
        c = lambda v: {"type": "choice", "choice": v, "confidence": conf}  # noqa: E731
        a = {k: {"type": "noul", "noul": nouls.get(k, 0.1)} for k, q in questions.items() if q["type"] == "noul"}
        a |= {"action": c(action), "group": c(group), "flow_kind": c(flow_kind), "context_kind": c(context_kind),
              "target": c(target), "other": c("s1"), "update_what": c("name"), "who": c(who),
              "label": c(spans[0]), "actor": c(actor if actor is not None else actors[0])}
        return a, "jev-test", 42
    return call, seen


def new_board(client, **kw):
    return client.post("/api/boards", headers=H, json={"title": "Arrears live", "session_pass": "detail", **kw}).json()


def say(client, b, text, **kw):
    return client.post(f"/api/boards/{b['id']}/live/utterance", headers=H,
                       json={"text": text, "doc": DOC, **kw})


def test_questions_stay_portable_and_add_applies(client, monkeypatch):
    enable(monkeypatch)
    sign_in(client, "lead@example.com.au")
    b = new_board(client)
    call, seen = fake_jev(workaround=0.9)
    monkeypatch.setattr(live_router.jev, "system_one", call)
    r = say(client, b, "Then I copy the unpaid ones into my arrears spreadsheet", last_touched="t1")
    assert r.status_code == 200, r.text
    for q in seen["questions"].values():
        assert len(q.get("criteria", {})) <= 20
    assert seen["state"]["last_changed_element"] == "Check bank feed"
    op = r.json()["ops"][0]
    assert op["op"] == "add" and op["kind"] == "workaround" and op["after"] == "t1" and op["auto"] is True


def test_overview_keeps_standard_path_and_parks_the_rest(client, monkeypatch):
    enable(monkeypatch)
    sign_in(client, "lead@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Overview"}).json()
    assert b["session_pass"] == "overview"
    call, seen = fake_jev(group="context", context_kind="issue", issue=0.9)
    monkeypatch.setattr(live_router.jev, "system_one", call)
    r = say(client, b, "The bank feed is often a day behind").json()
    assert r["ops"] == [] and {p["category"] for p in r["parking"]} == {"issue"}
    assert set(seen["questions"]["flow_kind"]["criteria"]) == {"start", "task", "subprocess", "decision", "end"}
    call, _ = fake_jev(group="step", flow_kind="task", states_rule=0.9)
    monkeypatch.setattr(live_router.jev, "system_one", call)
    r = say(client, b, "If they're more than a week late I send a notice").json()
    assert r["ops"] and r["parking"][0]["category"] == "rule"
    items = client.get(f"/api/boards/{b['id']}/parking").json()
    assert len(items) == 2
    assert client.patch(f"/api/parking/{items[0]['id']}", headers=H, json={"status": "placed"}).json()["status"] == "placed"


def test_outside_party_and_cause(client, monkeypatch):
    enable(monkeypatch)
    sign_in(client, "lead@example.com.au")
    b = new_board(client)
    call, _ = fake_jev(group="context", context_kind="external_party", actor=None, from_outside=0.9)
    monkeypatch.setattr(live_router.jev, "system_one", call)
    op = say(client, b, "The tenant pays by bank transfer").json()["ops"][0]
    assert op["kind"] == "external_party" and op["direction"] == "in"
    call, _ = fake_jev(group="step", flow_kind="task", who="outside_party", from_outside=0.9)
    monkeypatch.setattr(live_router.jev, "system_one", call)
    op = say(client, b, "The bank sends the statement").json()["ops"][0]
    assert op["party"] and op["direction"] == "in"
    call, _ = fake_jev(group="context", context_kind="issue", target="i1", is_cause=0.9)
    monkeypatch.setattr(live_router.jev, "system_one", call)
    op = say(client, b, "That's because the bank only updates overnight").json()["ops"][0]
    assert op["relation"] == "cause" and op["after"] == "i1"


def test_low_confidence_waits_and_remove_never_auto(client, monkeypatch):
    enable(monkeypatch)
    sign_in(client, "lead@example.com.au")
    b = new_board(client)
    call, _ = fake_jev(conf=0.5)
    monkeypatch.setattr(live_router.jev, "system_one", call)
    assert say(client, b, "we might ring them").json()["ops"][0]["auto"] is False
    call, _ = fake_jev(action="remove", conf=0.99)
    monkeypatch.setattr(live_router.jev, "system_one", call)
    op = say(client, b, "we don't check the bank feed any more").json()["ops"][0]
    assert op["op"] == "remove" and op["auto"] is False


def test_command_mode_ignores_description(client, monkeypatch):
    enable(monkeypatch)
    sign_in(client, "lead@example.com.au")
    b = new_board(client)
    call, _ = fake_jev()
    monkeypatch.setattr(live_router.jev, "system_one", call)
    assert say(client, b, "I check the feed", mode="command").json()["ops"] == []


def test_personal_info_blocks_hosted_jev(client, monkeypatch):
    enable(monkeypatch)
    sign_in(client, "lead@example.com.au")
    b = new_board(client, personal_info=True)
    assert say(client, b, "x").status_code == 409
    enable(monkeypatch, decision_is_local=True)
    call, _ = fake_jev()
    monkeypatch.setattr(live_router.jev, "system_one", call)
    assert say(client, b, "x y z").status_code == 200


def test_actor_candidates_are_short():
    from app.live.spans import actor_candidates
    c = actor_candidates("The tenant pays Dean by bank transfer")
    assert "Dean" in c[:3] and "Tenant" in c and all(len(x.split()) <= 3 for x in c)


def test_structure_checks(client):
    sign_in(client, "lead@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Checks"}).json()
    doc = {"nodes": [
        {"id": "s", "type": "bpmnStart", "position": {"x": 0, "y": 0}, "data": {"label": "Rent due"}},
        {"id": "t", "type": "bpmnTask", "position": {"x": 100, "y": 0}, "data": {"label": "Check feed"}},
        {"id": "g", "type": "bpmnGateway", "position": {"x": 200, "y": 0}, "data": {"label": "Paid",
                                                                                     "gatewayType": "exclusive"}},
        {"id": "r", "type": "bpmnTask", "position": {"x": 300, "y": 0}, "data": {"label": "Decide on notice",
                                                                                  "taskKind": "rule"}},
        {"id": "p", "type": "bpmnGateway", "position": {"x": 400, "y": 0}, "data": {"gatewayType": "parallel"}},
    ], "edges": [{"id": "1", "source": "s", "target": "t"}, {"id": "2", "source": "t", "target": "g"},
                 {"id": "3", "source": "g", "target": "r"}, {"id": "4", "source": "g", "target": "t", "label": "No"},
                 {"id": "5", "source": "r", "target": "p"}, {"id": "6", "source": "p", "target": "s"},
                 {"id": "7", "source": "p", "target": "t"}]}
    found = " | ".join(c["text"] for c in client.post(f"/api/boards/{b['id']}/checks", headers=H,
                                                       json={"doc": doc}).json())
    for expected in ("no end event", "without an answer", "as a question", "parallel split", "loops back",
                     "no rule table"):
        assert expected in found, expected


def test_rules_are_normalised(client):
    sign_in(client, "lead@example.com.au")
    b = new_board(client)
    rules = [{"name": "Breach notice", "inputs": ["days late", "payment plan"], "output": "notice",
              "rows": [{"when": {"days late": "more than 7", "payment plan": "no", "ignored": "x"}, "then": "issue"}]},
             {"name": ""}]
    out = client.put(f"/api/boards/{b['id']}/rules", headers=H, json={"rules": rules}).json()
    assert len(out) == 1 and out[0]["rows"][0]["when"] == {"days late": "more than 7", "payment plan": "no"}
    assert client.get(f"/api/boards/{b['id']}/rules").json()[0]["id"].startswith("rule-")


def test_review_validates_changes_rules_and_parking(client, monkeypatch):
    enable(monkeypatch)
    sign_in(client, "lead@example.com.au")
    b = new_board(client)
    call, _ = fake_jev(states_rule=0.9)
    monkeypatch.setattr(live_router.jev, "system_one", call)
    parked = say(client, b, "Over a week late and Dean approves the notice").json()["parking"][0]
    out = {"summary": "Tidied.", "document": "# Arrears\n1. Check bank feed", "open_questions": ["What counts as late?"],
           "parking_done": [parked["id"], "not-a-real-id"],
           "rules": [{"name": "Breach notice", "element_id": "r2", "inputs": ["days late"], "output": "notice",
                      "rows": [{"when": {"days late": "over a week"}, "then": "issue, Dean approves"}]}],
           "changes": [
               {"op": "update", "id": "t1", "label": "Check bank feed for payments", "reason": "clearer"},
               {"op": "add", "ref": "r1", "kind": "external_party", "label": "Tenant"},
               {"op": "add", "ref": "r2", "kind": "rule_task", "label": "Decide on breach notice", "after": "t1"},
               {"op": "add", "ref": "r3", "kind": "issue", "label": "Bank updates overnight", "cause_of": "i1"},
               {"op": "connect", "from": "t1", "to": "r1", "flow": "message"},
               {"op": "update", "id": "ghost", "label": "nope"},
               {"op": "add", "kind": "spaceship", "label": "nope"},
               {"op": "remove", "id": "s1", "reason": "duplicate"}]}
    captured = {}

    def fake_complete(system, user, json_mode=True):
        captured["system"], captured["prompt"] = system, user
        return json.dumps(out), "ollama", "m"
    monkeypatch.setattr(rv, "complete", fake_complete)
    monkeypatch.setattr(rv, "is_local", lambda: True)
    r = client.post(f"/api/boards/{b['id']}/live/review", headers=H, json={"doc": DOC, "doc_kind": "wi"})
    assert r.status_code == 200, r.text
    prop = r.json()["proposal"]
    ch = prop["changes"]
    assert [c["op"] for c in ch] == ["update", "add", "add", "add", "connect", "remove"]
    assert ch[3]["relation"] == "cause" and ch[3]["after"] == "i1"
    assert ch[4]["flow"] == "message" and all(c["auto"] is False for c in ch)
    assert prop["rules"][0]["element_id"] == ch[2]["ref"]
    assert prop["parking_done"] == [parked["id"]]
    assert "DETAIL pass" in captured["system"] and "PARKING LOT" in captured["prompt"]
    assert parked["id"] in captured["prompt"]


def test_combine_views(client, monkeypatch):
    sign_in(client, "lead@example.com.au")
    procs = client.get("/api/processes").json()
    pid = next(p for p in procs if p["name"] == "Maintenance and repairs")["id"]
    assert client.post(f"/api/processes/{pid}/combine", headers=H).status_code == 409
    for who in ("Property manager", "Contractor coordinator"):
        client.post("/api/boards", headers=H, json={"title": f"{who} view", "process_id": pid, "perspective": who})
    out = {"summary": "Joined at the job hand-off.", "changes": [
        {"op": "add", "ref": "a", "kind": "start", "label": "Repair reported", "lane": "Property manager"},
        {"op": "add", "ref": "b", "kind": "task", "label": "Book contractor", "lane": "Contractor coordinator",
         "after": "a"},
        {"op": "connect", "from": "a", "to": "b"}, {"op": "remove", "id": "a"}]}
    monkeypatch.setattr(cb, "complete", lambda s, u, json_mode=True: (json.dumps(out), "ollama", "m"))
    monkeypatch.setattr(cb, "is_local", lambda: True)
    r = client.post(f"/api/processes/{pid}/combine", headers=H)
    assert r.status_code == 200, r.text
    drafts = client.get(f"/api/boards/{r.json()['id']}/drafts").json()
    assert drafts[0]["mode"] == "combine"
    assert [c["op"] for c in drafts[0]["proposal"]["changes"]] == ["add", "add", "connect"]
    assert all(c["auto"] for c in drafts[0]["proposal"]["changes"])


def test_new_columns_added_to_old_database(tmp_path):
    import sqlite3

    from sqlalchemy import create_engine, inspect

    from app import db as dbmod
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("create table boards (id varchar(32) primary key, title varchar(300))")
    con.commit()
    con.close()
    old_engine = dbmod._engine
    dbmod._engine = create_engine(f"sqlite:///{path}")
    try:
        dbmod.init_db()
        cols = {c["name"] for c in inspect(dbmod._engine).get_columns("boards")}
        assert {"document_markdown", "session_pass", "perspective", "rules"} <= cols
    finally:
        dbmod._engine = old_engine
