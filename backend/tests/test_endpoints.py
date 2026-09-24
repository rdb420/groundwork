"""Every state-changing endpoint: who may call it, what it changes, and that it is audited
(CLAUDE.md). Behaviour-heavy endpoints (live mapping, review, combine) also have their own tests
in test_live.py."""
import json

from app.config import get_settings
from tests.conftest import audited, sign_in

H = {"x-requested-with": "groundwork"}


def upload(client, title="Checklist", **meta):
    return client.post("/api/artifacts", headers=H, files={"file": ("list.txt", title.encode(), "text/plain")},
                       data={"meta": json.dumps({"title": title, "personal_info": "no", **meta})})


def test_logout_ends_the_session_and_is_audited(client):
    sign_in(client, "leaver@example.com.au")
    before = audited("auth.signed_out")
    assert client.post("/api/auth/logout", headers=H).status_code == 200
    assert audited("auth.signed_out") == before + 1
    assert client.get("/api/auth/me").status_code == 401


def test_profile_update_is_audited(client):
    sign_in(client, "newstarter@example.com.au")
    me = client.get("/api/auth/me").json()
    assert client.put("/api/auth/me", headers=H, json={"display_name": "Priya", "team": "Accounts"}).status_code == 200
    assert audited("user.profile_updated", me["id"]) == 1


def test_withdraw_only_by_uploader_or_admin(client):
    sign_in(client, "staff@example.com.au")
    aid = upload(client).json()["id"]
    sign_in(client, "lead@example.com.au")  # analysts see everything but can't withdraw others' files
    assert client.post(f"/api/artifacts/{aid}/withdraw", headers=H).status_code == 403
    sign_in(client, "staff@example.com.au")
    assert client.post(f"/api/artifacts/{aid}/withdraw", headers=H).status_code == 200
    assert audited("artifact.withdrawn", aid) == 1
    assert all(a["id"] != aid for a in client.get("/api/artifacts").json())

    aid2 = upload(client, "Another").json()["id"]
    sign_in(client, "boss@example.com.au")
    assert client.post(f"/api/artifacts/{aid2}/withdraw", headers=H).status_code == 200


def test_download_is_audited_and_private(client):
    sign_in(client, "staff@example.com.au")
    aid = upload(client, "Private notes").json()["id"]
    r = client.get(f"/api/artifacts/{aid}/file")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert audited("artifact.downloaded", aid) == 1
    sign_in(client, "other@example.com.au")
    assert client.get(f"/api/artifacts/{aid}/file").status_code == 404


def test_process_create_and_edit_permissions(client):
    sign_in(client, "staff@example.com.au")
    r = client.post("/api/processes", headers=H, json={"name": "Key handover"})
    pid = r.json()["id"]
    assert audited("process.proposed", pid) == 1
    again = client.post("/api/processes", headers=H, json={"name": "key HANDOVER"}).json()
    assert again == {"id": pid, "name": "Key handover", "existing": True}
    assert client.patch(f"/api/processes/{pid}", headers=H, json={"status": "confirmed"}).status_code == 403
    sign_in(client, "lead@example.com.au")
    assert client.patch(f"/api/processes/{pid}", headers=H, json={"status": "confirmed"}).status_code == 200
    assert audited("process.updated", pid) == 1
    assert next(p for p in client.get("/api/processes").json() if p["id"] == pid)["status"] == "confirmed"


def test_admin_endpoints_need_roles(client):
    sign_in(client, "staff@example.com.au")
    assert client.get("/api/admin/overview").status_code == 403
    assert client.get("/api/admin/audit").status_code == 403
    sign_in(client, "lead@example.com.au")
    assert client.get("/api/admin/overview").status_code == 200
    assert client.get("/api/admin/audit").status_code == 403
    sign_in(client, "boss@example.com.au")
    assert client.get("/api/admin/audit").status_code == 200


def test_board_create_save_and_draft_decisions_are_audited(client):
    sign_in(client, "lead@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Bond refunds"}).json()
    assert audited("board.created", b["id"]) == 1
    r = client.put(f"/api/boards/{b['id']}", headers=H, json={"version": 1, "doc": {"nodes": [], "edges": []}})
    assert r.status_code == 200 and audited("board.saved", b["id"]) == 1
    assert client.post("/api/drafts/nope/accept", headers=H).status_code == 404
    assert client.post("/api/drafts/nope/maybe", headers=H).status_code == 404


def test_recording_chunks_end_and_audit(client):
    sign_in(client, "lead@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Inspections"}).json()
    rec = client.post(f"/api/boards/{b['id']}/recordings", headers=H, json={"consent_note": "Sam agreed"}).json()
    assert audited("recording.started", rec["id"]) == 1
    r = client.post(f"/api/recordings/{rec['id']}/chunks?seq=0", headers=H, files={"file": ("c.webm", b"\x1a\x45")})
    assert r.status_code == 200 and audited("recording.chunk_received", rec["id"]) == 1
    assert client.post(f"/api/recordings/{rec['id']}/end", headers=H).status_code == 200
    assert audited("recording.ended", rec["id"]) == 1


def test_session_settings_parking_and_document(client, monkeypatch):
    sign_in(client, "lead@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Arrears"}).json()
    bid = b["id"]
    r = client.patch(f"/api/boards/{bid}/settings", headers=H, json={"session_pass": "detail", "perspective": "Sam"})
    assert r.status_code == 200 and r.json()["session_pass"] == "detail" and audited("board.settings", bid) == 1
    assert client.patch(f"/api/boards/{bid}/settings", headers=H, json={"session_pass": "sideways"}).status_code == 422

    p = client.post(f"/api/boards/{bid}/parking", headers=H, json={"category": "issue", "text": "Feed is late"})
    assert p.status_code == 200 and audited("parking.added", p.json()["id"]) == 1
    assert client.post(f"/api/boards/{bid}/parking", headers=H, json={"category": "gossip", "text": "x"}).status_code == 422
    r = client.patch(f"/api/parking/{p.json()['id']}", headers=H, json={"status": "placed"})
    assert r.json()["status"] == "placed" and audited("parking.updated", p.json()["id"]) == 1
    assert client.patch(f"/api/parking/{p.json()['id']}", headers=H, json={"status": "lost"}).status_code == 422

    r = client.put(f"/api/boards/{bid}/document", headers=H, json={"markdown": "# SOP", "doc_kind": "sop", "version": 0})
    assert r.status_code == 200 and audited("board.document_saved", bid) == 1
    assert client.get(f"/api/boards/{bid}/document").json()["markdown"] == "# SOP"


def test_live_sentences_are_always_audited(client, monkeypatch):
    from app.routers import live as live_router
    s = get_settings()
    monkeypatch.setattr(s, "decision_provider", "jev")
    sign_in(client, "lead@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Small talk", "session_pass": "detail"}).json()

    def nothing(state, questions):
        return {"action": {"type": "choice", "choice": "nothing", "confidence": 0.9}}, "jev-test", 5

    monkeypatch.setattr(live_router.jev, "system_one", nothing)
    r = client.post(f"/api/boards/{b['id']}/live/utterance", headers=H,
                    json={"text": "Lovely weather today", "doc": {"nodes": [], "edges": []}})
    assert r.status_code == 200 and r.json()["ops"] == []
    assert audited("live.heard", b["id"]) == 1


def test_every_mutating_route_writes_an_audit_event():
    """CLAUDE.md: every state-changing endpoint calls audit.record. Read-only POSTs are listed here."""
    import inspect

    from tests.conftest import api_routes
    read_only = {"/api/boards/{bid}/checks"}
    mutating = [r for r in api_routes() if r.methods & {"POST", "PUT", "PATCH", "DELETE"}]
    assert len(mutating) > 25  # the scan must actually see the routes
    missing = [r.path for r in mutating if r.path not in read_only and "audit.record" not in inspect.getsource(r.endpoint)]
    assert missing == []
