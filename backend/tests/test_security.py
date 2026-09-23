"""Hardening from the pre-pilot audit (docs/AUDIT.md, H1 to H4 and the medium and low items)."""
import json

from tests.conftest import sign_in

H = {"x-requested-with": "groundwork"}
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(document.cookie)</script></svg>'


def board_image(client, bid, name, body, claimed_type):
    return client.post("/api/artifacts", headers=H, files={"file": (name, body, claimed_type)},
                       data={"meta": json.dumps({"title": name, "board_id": bid})})


# ---- H1: stored XSS --------------------------------------------------------------------

def test_security_headers_on_every_response(client):
    r = client.get("/api/health")
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp and "object-src 'none'" in csp
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_svg_downloads_sandboxed_and_claimed_types_are_ignored(client):
    sign_in(client, "staff@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Images"}).json()
    svg = board_image(client, b["id"], "sketch.svg", SVG, "image/svg+xml").json()
    fake_png = board_image(client, b["id"], "photo.png", SVG, "image/svg+xml").json()

    sign_in(client, "colleague@example.com.au")  # board images are visible to anyone with the map
    r = client.get(f"/api/artifacts/{svg['id']}/file")
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith("attachment")
    assert "sandbox" in r.headers["content-security-policy"]
    r = client.get(f"/api/artifacts/{fake_png['id']}/file")
    assert r.headers["content-type"] == "image/png"  # never the browser's claim
    assert r.headers["content-disposition"].startswith("inline")
    assert r.headers["x-content-type-options"] == "nosniff"


def test_only_images_go_on_maps_and_references_must_exist(client):
    sign_in(client, "staff@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Images"}).json()
    assert board_image(client, b["id"], "notes.html", b"<script>x</script>", "text/html").status_code == 415
    assert board_image(client, "no-such-map", "photo.png", b"\x89PNG", "image/png").status_code == 404
    r = client.post("/api/artifacts", headers=H, files={"file": ("a.txt", b"a", "text/plain")},
                    data={"meta": json.dumps({"title": "a", "process_ids": ["no-such-process"]})})
    assert r.status_code == 404


# ---- H3: "unsure" counts as personal information --------------------------------------

def test_unsure_files_stay_out_of_cloud_models(client, monkeypatch):
    from app.ai import generate as gen
    monkeypatch.setattr(gen, "is_local", lambda: False)
    monkeypatch.setattr(gen, "complete", lambda *a, **k: ('{"markdown": "x"}', "anthropic", "m"))
    sign_in(client, "lead@example.com.au")
    pid = client.post("/api/processes", headers=H, json={"name": "Unsure evidence"}).json()["id"]
    b = client.post("/api/boards", headers=H, json={"title": "Unsure", "process_id": pid}).json()

    def upload(pi):
        return client.post("/api/artifacts", headers=H, files={"file": ("f.txt", pi.encode(), "text/plain")},
                           data={"meta": json.dumps({"title": pi, "personal_info": pi, "process_ids": [pid]})}).json()

    no = upload("no")
    assert client.post(f"/api/boards/{b['id']}/generate", headers=H, json={"mode": "sop"}).status_code == 200
    unsure = upload("unsure")
    r = client.post(f"/api/boards/{b['id']}/generate", headers=H, json={"mode": "sop"})
    assert r.status_code == 409 and "personal information" in r.json()["detail"]
    for a in (no, unsure):
        client.post(f"/api/artifacts/{a['id']}/withdraw", headers=H)


# ---- H2: one bad map breaks a board ----------------------------------------------------

def task(nid, x=0, **kw):
    return {"id": nid, "type": "bpmnTask", "position": {"x": x, "y": 0}, "data": {"label": nid}, **kw}


def test_bad_maps_are_refused_on_save(client):
    sign_in(client, "lead@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Validation"}).json()

    def save(nodes, edges=()):
        return client.put(f"/api/boards/{b['id']}", headers=H, json={"version": 1, "doc": {"nodes": nodes, "edges": list(edges)}})

    assert save([{"type": "bpmnTask", "position": {"x": 0, "y": 0}}]).status_code == 422  # no id
    assert save([task("a"), task("a")]).status_code == 422  # duplicate id
    assert save([{"id": "a", "type": "bpmnTask"}]).status_code == 422  # no position
    assert save([task("a", parentId="b"), task("b", parentId="a")]).status_code == 422  # parent loop
    assert save([task("a", parentId="gone")]).status_code == 422
    r = save([task("a"), task("b")], [{"id": "e1", "source": "a", "target": "b"}, {"id": "e2", "source": "a", "target": "gone"}])
    assert r.status_code == 200
    assert [e["id"] for e in client.get(f"/api/boards/{b['id']}").json()["doc"]["edges"]] == ["e1"]
    assert client.post(f"/api/boards/{b['id']}/checks", headers=H,
                       json={"doc": {"nodes": [{"type": "x"}], "edges": []}}).status_code == 422


def test_long_chains_and_parent_loops_do_not_crash(client):
    from app.ai.context import describe_board, structure_checks
    sign_in(client, "lead@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Long"}).json()
    nodes = [{"id": "s", "type": "bpmnStart", "position": {"x": 0, "y": 0}}] + [task(f"n{i}", i * 10) for i in range(1800)]
    edges = [{"id": "e", "source": "s", "target": "n0"}] + [{"id": f"e{i}", "source": f"n{i}", "target": f"n{i + 1}"} for i in range(1799)]
    edges.append({"id": "back", "source": "n1799", "target": "n5"})
    r = client.post(f"/api/boards/{b['id']}/checks", headers=H, json={"doc": {"nodes": nodes, "edges": edges}})
    assert r.status_code == 200
    assert any("loops back" in c["text"] for c in r.json())
    # Maps saved before validation can still hold a loop; the text builder must not recurse forever.
    loop = {"nodes": [task("a", parentId="b"), task("b", parentId="a")], "edges": []}
    assert "ELEMENTS" in describe_board(loop) and structure_checks(loop) is not None


def test_damaged_saved_map_gives_a_clear_message(client, monkeypatch):
    from app.ai import generate as gen
    from app.db import SessionLocal
    from app.models import Board
    monkeypatch.setattr(gen, "is_local", lambda: True)
    sign_in(client, "lead@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Legacy"}).json()
    with SessionLocal() as db:
        db.get(Board, b["id"]).doc = {"nodes": [{"type": "bpmnTask"}], "edges": []}
        db.commit()
    r = client.post(f"/api/boards/{b['id']}/generate", headers=H, json={"mode": "sop"})
    assert r.status_code == 409 and "damaged data" in r.json()["detail"]


# ---- H4: recordings --------------------------------------------------------------------

def test_recording_parts_are_kept_safe(client, monkeypatch):
    from datetime import timedelta

    from app.config import get_settings
    from app.db import SessionLocal
    from app.models import Recording
    from app.routers import boards as boards_router
    from app.security import utcnow
    sign_in(client, "lead@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Recording"}).json()
    rid = client.post(f"/api/boards/{b['id']}/recordings", headers=H, json={"consent_note": "Sam agreed"}).json()["id"]

    def part(seq, body=b"audio", name="chunk.webm"):
        return client.post(f"/api/recordings/{rid}/chunks?seq={seq}", headers=H, files={"file": (name, body)})

    first = part(0, b"FIRST").json()
    again = part(0, b"SECOND")  # a retry of the same part
    assert again.status_code == 200 and again.json()["segment_id"] == first["segment_id"]
    audio = get_settings().data_dir / "recordings" / rid / "00000.webm"
    assert audio.read_bytes() == b"FIRST"
    assert part(-1).status_code == 422
    assert part(1, name="evil.html").status_code == 200
    assert (get_settings().data_dir / "recordings" / rid / "00001.webm").exists()  # never .html
    monkeypatch.setattr(boards_router, "CHUNK_LIMIT", 10)
    assert part(2, b"x" * 11).status_code == 413
    monkeypatch.setattr(boards_router, "CHUNK_LIMIT", 25 * 1024 * 1024)

    sign_in(client, "colleague@example.com.au")
    assert part(3).status_code == 403
    assert client.post(f"/api/recordings/{rid}/end", headers=H).status_code == 403

    sign_in(client, "lead@example.com.au")
    assert client.post(f"/api/recordings/{rid}/end", headers=H).status_code == 200
    assert part(3).status_code == 200  # the last part can land just after Stop
    with SessionLocal() as db:
        db.get(Recording, rid).ended_at = utcnow() - timedelta(minutes=5)
        db.commit()
    assert part(4).status_code == 409
    assert client.post(f"/api/recordings/{rid}/end", headers=H).status_code == 200  # ending twice is fine


# ---- M5: one new process per name ------------------------------------------------------

def test_a_batch_with_a_new_process_name_creates_it_once(client):
    sign_in(client, "staff@example.com.au")
    meta = {"personal_info": "no", "new_process_names": ["Key register upkeep"]}
    for i in range(3):
        client.post("/api/artifacts", headers=H, files={"file": (f"f{i}.txt", f"f{i}".encode(), "text/plain")},
                    data={"meta": json.dumps({"title": f"File {i}", **meta})})
    named = [p for p in client.get("/api/processes").json() if p["name"] == "Key register upkeep"]
    assert len(named) == 1 and named[0]["artifact_count"] == 3
    client.post("/api/artifacts", headers=H, files={"file": ("g.txt", b"g", "text/plain")},
                data={"meta": json.dumps({"title": "Other case", "personal_info": "no",
                                          "new_process_names": ["KEY REGISTER UPKEEP"]})})
    assert len([p for p in client.get("/api/processes").json() if p["name"].lower() == "key register upkeep"]) == 1


# ---- M6: roles and sessions ------------------------------------------------------------

def test_roles_follow_config_and_admins_can_revoke(client, monkeypatch):
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "analyst_emails", s.analyst_emails + ",temp-analyst@example.com.au")
    sign_in(client, "temp-analyst@example.com.au")
    assert client.get("/api/auth/me").json()["role"] == "analyst"
    monkeypatch.setattr(s, "analyst_emails", "lead@example.com.au")
    assert client.get("/api/auth/me").json()["role"] == "contributor"  # no new sign-in needed
    assert client.get("/api/admin/coverage").status_code == 403

    sign_in(client, "leaving@example.com.au")
    me = client.get("/api/auth/me").json()
    leaver_cookie = client.cookies.get("gw_session")
    sign_in(client, "boss@example.com.au")
    boss = client.get("/api/auth/me").json()
    people = client.get("/api/admin/users").json()
    assert next(p for p in people if p["id"] == me["id"])["sessions"] >= 1
    assert client.post(f"/api/admin/users/{me['id']}/sign-out", headers=H).json()["sessions"] >= 1
    assert client.post(f"/api/admin/users/{boss['id']}/access", headers=H, json={"blocked": True}).status_code == 422
    assert client.post(f"/api/admin/users/{me['id']}/access", headers=H, json={"blocked": True}).status_code == 200

    client.cookies.clear()
    client.cookies.set("gw_session", leaver_cookie)
    assert client.get("/api/auth/me").status_code == 401
    from tests.conftest import SENT
    SENT.pop("leaving@example.com.au", None)
    client.post("/api/auth/request", json={"email": "leaving@example.com.au"})
    assert "leaving@example.com.au" not in SENT  # no link for someone whose access was removed

    sign_in(client, "boss@example.com.au")
    client.post(f"/api/admin/users/{me['id']}/access", headers=H, json={"blocked": False})
    sign_in(client, "leaving@example.com.au")
    assert client.get("/api/auth/me").status_code == 200


def test_housekeeping_clears_expired_sessions_and_links():
    from datetime import timedelta

    from app import housekeeping
    from app.db import SessionLocal
    from app.models import MagicToken, Session, User
    from app.security import utcnow
    with SessionLocal() as db:
        u = User(email="old@example.com.au")
        db.add(u)
        db.flush()
        db.add(Session(token_hash="x" * 64, user_id=u.id, expires_at=utcnow() - timedelta(days=1)))
        db.add(MagicToken(email=u.email, token_hash="y" * 64, expires_at=utcnow() - timedelta(days=2)))
        db.commit()
        done = housekeeping.run(db)
        db.commit()
    assert done["sessions"] >= 1 and done["tokens"] >= 1


# ---- M9: one access point for maps ------------------------------------------------------

def test_every_map_route_goes_through_open_board(client, monkeypatch):
    from app import access
    from tests.conftest import api_routes
    sign_in(client, "lead@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Private"}).json()
    bid = b["id"]
    rid = client.post(f"/api/boards/{bid}/recordings", headers=H, json={"consent_note": "Sam agreed"}).json()["id"]
    park = client.post(f"/api/boards/{bid}/parking", headers=H, json={"category": "issue", "text": "x"}).json()["id"]
    img = board_image(client, bid, "p.png", b"\x89PNG", "image/png").json()["id"]
    from app.db import SessionLocal
    from app.models import AIDraft
    with SessionLocal() as db:
        d = AIDraft(board_id=bid, requested_by=client.get("/api/auth/me").json()["id"], mode="sop", provider="x",
                    model="x", board_version=1)
        db.add(d)
        db.commit()
        did = d.id

    sign_in(client, "outsider@example.com.au")
    monkeypatch.setattr(access, "can_open_board", lambda board, user: False)
    ids = {"bid": bid, "rid": rid, "pid": park, "did": did, "decision": "accept", "aid": img}
    doc = {"doc": {"nodes": [], "edges": []}, "text": "hello", "rules": [], "markdown": "x", "version": 1,
           "consent_note": "Sam agreed", "category": "issue", "status": "open", "mode": "sop"}
    checked = []
    for r in api_routes():
        if not any(k in r.path for k in ("{bid}", "{rid}", "{did}", "/parking/{pid}")):
            continue
        if r.path.startswith("/api/admin"):
            continue
        url = r.path.format(**ids)
        for method in r.methods:
            if method == "GET":
                res = client.get(url)
            elif "chunks" in url:
                res = client.post(url + "?seq=9", headers=H, files={"file": ("c.webm", b"x")})
            else:
                res = client.request(method, url, headers=H, json=doc)
            checked.append(url)
            assert res.status_code == 404, (method, url, res.status_code, res.text)
    assert client.get(f"/api/artifacts/{img}/file").status_code == 404
    assert all(x["id"] != bid for x in client.get("/api/boards").json())
    assert len(checked) >= 20
