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
