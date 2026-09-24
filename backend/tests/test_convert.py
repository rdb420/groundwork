"""Phase 1 of the ingestion pipeline: every file type reaches the right converter, outputs land in
storage as a new document, and the malware check always comes first."""
import io
import json
import socketserver
import threading

import httpx
import pytest
from openpyxl import Workbook
from pypdf import PdfWriter
from sqlalchemy import select

from app import httpclient, worker
from app.config import get_settings
from app.db import SessionLocal
from app.ingest import blocks as B
from app.ingest import mineru
from app.models import Artifact, Document, Job
from app.storage import get_storage
from tests.conftest import sign_in
from tests.fakes import FakeGotenberg, FakeMinerU

H = {"x-requested-with": "groundwork"}


@pytest.fixture
def services(client, monkeypatch):
    fake_mineru, fake_gotenberg = FakeMinerU(), FakeGotenberg()
    monkeypatch.setitem(httpclient.TRANSPORTS, "mineru", httpx.MockTransport(fake_mineru))
    monkeypatch.setitem(httpclient.TRANSPORTS, "gotenberg", httpx.MockTransport(fake_gotenberg))
    monkeypatch.setattr(mineru.time, "sleep", lambda s: None)
    s = get_settings()
    for k, v in {"pipeline_enabled": True, "mineru_url": "http://mineru:8000", "gotenberg_url": "http://gotenberg:3000",
                 "embed_url": "", "mineru_page_batch": 50}.items():
        monkeypatch.setattr(s, k, v)
    drain()
    return fake_mineru, fake_gotenberg


def drain():
    from sqlalchemy import update
    while True:
        while worker.run_once():
            pass
        with SessionLocal() as db:
            waiting = db.execute(update(Job).where(Job.status == "queued").values(run_after=None)).rowcount
            db.commit()
        if not waiting:
            return


def share(client, name: str, data: bytes, **meta) -> str:
    r = client.post("/api/artifacts", headers=H, files={"file": (name, data)},
                    data={"meta": json.dumps({"title": name, "personal_info": "no", **meta})})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def document(aid: str) -> tuple[Artifact, Document | None]:
    with SessionLocal() as db:
        a = db.get(Artifact, aid)
        d = db.scalar(select(Document).where(Document.source_id == aid).order_by(Document.created_at.desc()))
        return a, d


def xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Arrears"
    ws.append(["Tenant", "Room", "Owing"])
    ws.append(["A", 3, 120.0])
    hidden = wb.create_sheet("Lookups")
    hidden.sheet_state = "hidden"
    hidden.append(["x"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def pdf(pages: int) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_pdf_goes_to_mineru_and_lands_in_storage(client, services):
    fake, _ = services
    sign_in(client, "staff@example.com.au")
    aid = share(client, "lease.pdf", pdf(2))
    drain()
    a, d = document(aid)
    assert a.pipeline_status == "done" and d.status == "ok" and d.converter == "mineru:pipeline"
    assert fake.received[0]["form"]["return_content_list"] == "true"
    st = get_storage()
    assert st.read_bytes(d.markdown_key).startswith(b"# Residential tenancy agreement")
    blocks = json.loads(st.read_bytes(d.content_list_key))
    assert [b["type"] for b in blocks] == ["heading", "text", "table", "image"]  # page header dropped
    assert blocks[2]["rows"] == [["Room", "Rent"], ["3", "$220"]] and blocks[2]["page"] == 2
    assert st.exists(d.markdown_key.replace("document.md", "images/a.jpg"))


def test_long_pdfs_go_in_page_windows(client, services, monkeypatch):
    fake, _ = services
    monkeypatch.setattr(get_settings(), "mineru_page_batch", 2)
    sign_in(client, "staff@example.com.au")
    aid = share(client, "plan.pdf", pdf(5))
    drain()
    windows = [(r["form"].get("start_page_id"), r["form"].get("end_page_id")) for r in fake.received]
    assert windows == [("0", "1"), ("2", "3"), ("4", "4")]
    _, d = document(aid)
    pages = {b["page"] for b in json.loads(get_storage().read_bytes(d.content_list_key)) if b["type"] == "text"}
    assert pages == {1, 3, 5}  # shifted to whole-document page numbers


def test_each_format_uses_its_converter(client, services):
    fake, gotenberg = services
    sign_in(client, "staff@example.com.au")
    eml = (b"From: sam@example.com.au\r\nTo: dean@example.com.au\r\nSubject: Arrears this week\r\n"
           b"MIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=XX\r\n\r\n--XX\r\n"
           b"Content-Type: text/plain\r\n\r\nThree rooms are behind.\r\n\r\nSee attached.\r\n--XX\r\n"
           b"Content-Type: text/csv\r\nContent-Disposition: attachment; filename=\"late.csv\"\r\n\r\n"
           b"Room,Days\r\n3,9\r\n--XX--\r\n")
    cases = {
        "tracker.xlsx": (xlsx(), "native:workbook"),
        "rooms.csv": (b"Room,Rent\n3,220\n", "native:delimited"),
        "notes.md": (b"# Steps\n\n- Check feed\n- Send reminder\n", "native:text"),
        "procedure.docx": (b"PK fake docx", "mineru:pipeline"),
        "old.doc": (b"\xd0\xcf fake doc", "gotenberg+mineru:pipeline"),
        "mail.eml": (eml, "native:email"),
        "plan.svg": (b'<svg xmlns="http://www.w3.org/2000/svg"><text>Room 3</text></svg>', "native:svg"),
    }
    ids = {name: share(client, name, data) for name, (data, _) in cases.items()}
    drain()
    for name, (_, converter) in cases.items():
        a, d = document(ids[name])
        assert d is not None and d.converter == converter, name
        assert a.pipeline_status == "done", name
    assert gotenberg.calls == 1
    blocks = json.loads(get_storage().read_bytes(document(ids["tracker.xlsx"])[1].content_list_key))
    assert blocks[0]["text"] == "Sheet: Arrears" and blocks[1]["rows"][1] == ["A", "3", "120"]
    assert blocks[2]["text"] == "Sheet: Lookups (hidden sheet)"
    mail_md = get_storage().read_bytes(document(ids["mail.eml"])[1].markdown_key).decode()
    assert "Arrears this week" in mail_md and "Attachment: late.csv" in mail_md and "| 3 | 9 |" in mail_md


def test_unsupported_and_audio_files(client, services):
    sign_in(client, "staff@example.com.au")
    heic = share(client, "photo.heic", b"fake")
    audio = share(client, "call.m4a", b"fake audio")
    drain()
    a, d = document(heic)
    assert a.pipeline_status == "skipped" and d.status == "skipped" and "JPEG" in d.note
    with SessionLocal() as db:
        assert db.scalar(select(Job).where(Job.kind == "transcribe_artifact", Job.ref_id == audio)) is not None


def test_rerunning_conversion_is_a_no_op(client, services):
    fake, _ = services
    sign_in(client, "staff@example.com.au")
    aid = share(client, "once.pdf", pdf(1))
    drain()
    with SessionLocal() as db:
        db.add(Job(kind="convert_artifact", ref_id=aid))
        db.commit()
    drain()
    with SessionLocal() as db:
        docs = db.scalars(select(Document).where(Document.source_id == aid)).all()
    assert len(docs) == 1 and len(fake.received) == 1


def test_mineru_failure_marks_the_file_failed(client, services):
    fake, _ = services
    fake.fail = True
    sign_in(client, "staff@example.com.au")
    aid = share(client, "broken.pdf", pdf(1))
    drain()
    a, _ = document(aid)
    assert a.pipeline_status == "failed" and a.status == "processed"  # the file itself is still shared


def test_the_malware_check_comes_first(client, services, monkeypatch):
    fake, _ = services

    class Clamd(socketserver.BaseRequestHandler):
        def handle(self):
            data = b""
            while not data.endswith(b"\0\0\0\0") or len(data) < 14:
                part = self.request.recv(65536)
                if not part:
                    break
                data += part
            self.request.sendall(b"stream: Eicar-Test-Signature FOUND\0")

    server = socketserver.TCPServer(("127.0.0.1", 0), Clamd)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(get_settings(), "clamav_host", "127.0.0.1")
    monkeypatch.setattr(get_settings(), "clamav_port", server.server_address[1])
    try:
        sign_in(client, "staff@example.com.au")
        aid = share(client, "eicar.pdf", b"X5O!P%@AP EICAR")
        drain()
    finally:
        server.shutdown()
        server.server_close()
    a, d = document(aid)
    assert a.status == "quarantined" and d is None and fake.received == []


def test_markdown_round_trip():
    md = "# Title\n\nPara one\nstill one.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n- x\n- y\n"
    blocks = B.from_markdown(md)
    assert [b["type"] for b in blocks] == ["heading", "text", "table", "list"]
    assert B.from_markdown(B.to_markdown(blocks)) == blocks
