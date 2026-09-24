"""Coverage view, process catalogue admin, retention and purge, and malware scanning (audit G4)."""
import json
import socketserver
import threading
from datetime import timedelta

import pytest

from app import worker
from app.config import get_settings
from app.db import SessionLocal
from app.models import Artifact, Recording
from app.security import utcnow
from tests.conftest import audited, sign_in

H = {"x-requested-with": "groundwork"}


def upload(client, title, **meta):
    r = client.post("/api/artifacts", headers=H, files={"file": (f"{title}.txt", title.encode(), "text/plain")},
                    data={"meta": json.dumps({"title": title, "personal_info": "no", **meta})})
    assert r.status_code == 200, r.text
    return r.json()


def drain(retries: bool = False):
    """Run every job. With retries, skip the backoff wait so failing jobs run to their last try."""
    from sqlalchemy import update

    from app.models import Job
    while True:
        while worker.run_once():
            pass
        if not retries:
            return
        with SessionLocal() as db:
            waiting = db.execute(update(Job).where(Job.status == "queued").values(run_after=None)).rowcount
            db.commit()
        if not waiting:
            return


def process_named(client, name):
    return next(p for p in client.get("/api/processes?include_retired=true").json() if p["name"] == name)


# ---- Coverage --------------------------------------------------------------------------

def test_coverage_counts_layers_maps_and_flags(client):
    sign_in(client, "lead@example.com.au")
    pid = client.post("/api/processes", headers=H, json={"name": "Coverage test process"}).json()["id"]
    upload(client, "Official procedure", layer="declared", process_ids=[pid])
    sign_in(client, "staff@example.com.au")
    upload(client, "My side sheet", layer="workaround", process_ids=[pid])
    gone = upload(client, "Withdrawn one", layer="actual", process_ids=[pid])
    client.post(f"/api/artifacts/{gone['id']}/withdraw", headers=H)
    assert client.get("/api/admin/coverage").status_code == 403

    sign_in(client, "lead@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Overview", "process_id": pid}).json()
    client.put(f"/api/boards/{b['id']}/document", headers=H,
               json={"markdown": "Step [TO CONFIRM: who] and [TO CONFIRM: when]", "doc_kind": "sop", "version": 0})
    cov = client.get("/api/admin/coverage").json()
    row = next(r for r in cov["processes"] if r["id"] == pid)
    assert row["layers"]["declared"] == 1 and row["layers"]["workaround"] == 1 and row["layers"]["actual"] == 0
    assert row["files"] == 2 and row["contributors"] == 2
    assert row["maps"]["overview"] == 1 and row["maps"]["to_confirm"] == 2
    assert "1 workaround" in row["flags"] and "Not mapped yet" not in row["flags"]
    assert cov["totals"]["to_confirm"] >= 2 and 0 < cov["totals"]["workaround_share"] <= 1
    assert any(c["email"] == "staff@example.com.au" for c in cov["contributors"])


# ---- Catalogue admin -------------------------------------------------------------------

def test_process_edits_are_validated(client):
    sign_in(client, "lead@example.com.au")
    a = client.post("/api/processes", headers=H, json={"name": "Catalogue A"}).json()["id"]
    b = client.post("/api/processes", headers=H, json={"name": "Catalogue B", "parent_id": a}).json()["id"]
    assert client.patch(f"/api/processes/{a}", headers=H, json={"status": "maybe"}).status_code == 422
    assert client.patch(f"/api/processes/{a}", headers=H, json={"parent_id": a}).status_code == 422
    assert client.patch(f"/api/processes/{a}", headers=H, json={"parent_id": b}).status_code == 422  # loop
    assert client.patch(f"/api/processes/{a}", headers=H, json={"name": "catalogue b"}).status_code == 409
    assert client.patch(f"/api/processes/{a}", headers=H, json={"owner_email": "not an email"}).status_code == 422
    r = client.patch(f"/api/processes/{a}", headers=H,
                     json={"name": "Catalogue A (renamed)", "owner_email": "Dean@Example.com.au", "status": "confirmed"})
    assert r.status_code == 200
    p = process_named(client, "Catalogue A (renamed)")
    assert p["owner_email"] == "dean@example.com.au" and p["status"] == "confirmed"
    assert client.patch(f"/api/processes/{b}", headers=H, json={"clear_parent": True}).status_code == 200
    assert process_named(client, "Catalogue B")["parent_id"] is None


def test_merge_moves_files_maps_and_children(client):
    sign_in(client, "lead@example.com.au")
    keep = client.post("/api/processes", headers=H, json={"name": "Bond lodgement"}).json()["id"]
    dup = client.post("/api/processes", headers=H, json={"name": "Lodging bonds"}).json()["id"]
    child = client.post("/api/processes", headers=H, json={"name": "Bond claims", "parent_id": dup}).json()["id"]
    both = upload(client, "Bond form", process_ids=[keep, dup])
    only = upload(client, "Bond checklist", process_ids=[dup])
    board = client.post("/api/boards", headers=H, json={"title": "Bonds", "process_id": dup}).json()
    assert client.post(f"/api/processes/{dup}/merge", headers=H, json={"into": dup}).status_code == 422
    assert client.post(f"/api/processes/{dup}/merge", headers=H, json={"into": child}).status_code == 422

    r = client.post(f"/api/processes/{dup}/merge", headers=H, json={"into": keep})
    assert r.status_code == 200 and r.json() == {"ok": True, "files": 1, "maps": 1}
    assert audited("process.merged", dup) == 1
    assert process_named(client, "Lodging bonds")["status"] == "retired"
    assert process_named(client, "Bond claims")["parent_id"] == keep
    assert client.get(f"/api/boards/{board['id']}").json()["process_id"] == keep
    for aid in (both["id"], only["id"]):
        assert [p["id"] for p in client.get(f"/api/artifacts/{aid}").json()["processes"]] == [keep]


# ---- Retention and purge ---------------------------------------------------------------

def test_retention_purges_withdrawn_files_and_old_audio(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "retention_withdrawn_days", 30)
    monkeypatch.setattr(s, "retention_audio_days", 90)
    sign_in(client, "staff@example.com.au")
    old = upload(client, "Old withdrawn")
    fresh = upload(client, "Fresh withdrawn")
    for a in (old, fresh):
        client.post(f"/api/artifacts/{a['id']}/withdraw", headers=H)
    sign_in(client, "lead@example.com.au")
    b = client.post("/api/boards", headers=H, json={"title": "Retention"}).json()
    rec = client.post(f"/api/boards/{b['id']}/recordings", headers=H, json={"consent_note": "Sam agreed"}).json()
    client.post(f"/api/recordings/{rec['id']}/chunks?seq=0", headers=H, files={"file": ("c.webm", b"\x1a\x45")})
    client.post(f"/api/recordings/{rec['id']}/end", headers=H)
    with SessionLocal() as db:
        db.get(Artifact, old["id"]).withdrawn_at = utcnow() - timedelta(days=31)
        db.get(Recording, rec["id"]).ended_at = utcnow() - timedelta(days=91)
        old_path = s.data_dir / db.get(Artifact, old["id"]).storage_key
        db.commit()
    audio_dir = s.data_dir / "recordings" / rec["id"]
    assert old_path.exists() and audio_dir.exists()

    assert client.get("/api/admin/retention").status_code == 403  # analysts can't purge
    sign_in(client, "boss@example.com.au")
    due = client.get("/api/admin/retention").json()
    assert [f["id"] for f in due["files"]] == [old["id"]] and [a["id"] for a in due["audio"]] == [rec["id"]]
    assert client.post("/api/admin/retention/run", headers=H).json() == {"files": 1, "audio": 1}
    assert not old_path.exists() and not old_path.parent.exists() and not audio_dir.exists()
    assert audited("artifact.purged", old["id"]) == 1 and audited("recording.audio_purged", rec["id"]) == 1
    with SessionLocal() as db:
        a = db.get(Artifact, old["id"])
        assert a.status == "purged" and a.profile is None and a.storage_key == ""
        assert db.get(Artifact, fresh["id"]).status == "withdrawn"
    assert client.get(f"/api/artifacts/{old['id']}/file").status_code == 410
    assert client.get("/api/admin/retention").json()["files"] == []


def test_admin_can_purge_one_file_now(client):
    sign_in(client, "staff@example.com.au")
    a = upload(client, "Tenant licence scan")
    sign_in(client, "lead@example.com.au")
    assert client.post(f"/api/admin/artifacts/{a['id']}/purge", headers=H, json={"reason": "ID"}).status_code == 403
    sign_in(client, "boss@example.com.au")
    assert client.post(f"/api/admin/artifacts/{a['id']}/purge", headers=H, json={"reason": ""}).status_code == 422
    r = client.post(f"/api/admin/artifacts/{a['id']}/purge", headers=H, json={"reason": "Holds a tenant's licence"})
    assert r.status_code == 200 and audited("artifact.purged", a["id"]) == 1
    assert client.post(f"/api/admin/artifacts/{a['id']}/purge", headers=H, json={"reason": "again"}).status_code == 409
    assert client.get(f"/api/artifacts/{a['id']}/file").status_code == 410


# ---- Malware scanning ------------------------------------------------------------------

class FakeClamd(socketserver.BaseRequestHandler):
    def handle(self):
        data = b""
        while not data.endswith(b"\0\0\0\0") or len(data) < 14:
            part = self.request.recv(65536)
            if not part:
                break
            data += part
        verdict = b"stream: Eicar-Test-Signature FOUND\0" if b"EICAR" in data else b"stream: OK\0"
        self.request.sendall(verdict)


@pytest.fixture
def clamd(monkeypatch):
    server = socketserver.TCPServer(("127.0.0.1", 0), FakeClamd)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    s = get_settings()
    monkeypatch.setattr(s, "clamav_host", "127.0.0.1")
    monkeypatch.setattr(s, "clamav_port", server.server_address[1])
    yield
    server.shutdown()
    server.server_close()


def test_scanner_quarantines_flagged_files(client, clamd):
    drain()
    sign_in(client, "staff@example.com.au")
    clean = upload(client, "Clean notes")
    bad = client.post("/api/artifacts", headers=H, files={"file": ("bad.txt", b"X5O!P%@AP EICAR-TEST", "text/plain")},
                      data={"meta": json.dumps({"title": "Bad", "personal_info": "no"})}).json()
    assert client.get(f"/api/artifacts/{clean['id']}/file").status_code == 409  # not checked yet
    drain()
    assert client.get(f"/api/artifacts/{clean['id']}").json()["scan"] == "clean"
    assert client.get(f"/api/artifacts/{clean['id']}/file").status_code == 200
    got = client.get(f"/api/artifacts/{bad['id']}").json()
    assert got["status"] == "quarantined" and got["scan"] == "infected"
    assert client.get(f"/api/artifacts/{bad['id']}/file").status_code == 403
    assert audited("artifact.quarantined", bad["id"]) == 1


def test_scanner_down_retries_then_fails(client, monkeypatch):
    drain()
    s = get_settings()
    monkeypatch.setattr(s, "clamav_host", "127.0.0.1")
    monkeypatch.setattr(s, "clamav_port", 1)  # nothing listens here
    sign_in(client, "staff@example.com.au")
    a = upload(client, "Waiting for the scanner")
    drain()
    got = client.get(f"/api/artifacts/{a['id']}").json()
    assert got["status"] == "received"  # waiting for its next try, not stuck on "reading"
    drain(retries=True)
    got = client.get(f"/api/artifacts/{a['id']}").json()
    assert got["status"] == "failed" and got["scan"] == ""
    assert client.get(f"/api/artifacts/{a['id']}/file").status_code == 409


# ---- M10: the worker --------------------------------------------------------------------

def test_worker_backs_off_reclaims_and_runs_transcription_first(client):
    from datetime import timedelta

    from app.models import Job
    drain(retries=True)
    with SessionLocal() as db:
        db.add_all([Job(kind="profile_artifact", ref_id="missing-file"),
                    Job(kind="transcribe_segment", ref_id="missing-segment")])
        stuck = Job(kind="profile_artifact", ref_id="missing-too", status="running", attempts=1,
                    updated_at=utcnow() - timedelta(hours=2))
        db.add(stuck)
        db.commit()
        stuck_id = stuck.id
    with SessionLocal() as db:
        first = worker.claim(db)
        assert first.kind == "transcribe_segment"  # a live session's transcript comes first
    assert worker.claim(SessionLocal(), ["transcribe_segment"]) is None  # that one is running now
    assert worker.reclaim() >= 1
    with SessionLocal() as db:
        assert db.get(Job, stuck_id).status == "queued"
    drain(retries=True)


def test_oversized_office_files_are_not_opened(tmp_path):
    import zipfile

    from app.processing import limits
    from app.processing.xlsx_profile import profile_workbook
    bomb = tmp_path / "bomb.xlsx"
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/worksheets/sheet1.xml", b"\0" * (20 * 1024 * 1024))  # compresses about 1000:1
    assert limits.too_big(bomb)
    assert "unusually large" in profile_workbook(bomb)["summary"]
    junk = tmp_path / "junk.xlsx"
    junk.write_bytes(b"not a zip")
    assert "isn't a valid Office file" in profile_workbook(junk)["summary"]


def test_large_workbooks_get_the_light_read(tmp_path, monkeypatch):
    from openpyxl import Workbook

    from app.processing import xlsx_profile
    wb = Workbook()
    wb.active.append(["a", "=1+1"])
    path = tmp_path / "big.xlsx"
    wb.save(path)
    monkeypatch.setattr(xlsx_profile, "LIGHT_ABOVE", 1)
    prof = xlsx_profile.profile_workbook(path)
    assert "light mode" in prof["summary"] and prof["sheets"][0]["formulas"] == 1
