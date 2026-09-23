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
