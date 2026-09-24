"""Sign-in email over SMTP with a password or OAuth 2.0 (SASL XOAUTH2), against a small in-process
SMTP server, and a clear reply when sending fails."""
import base64
import email
import email.policy
import json
import socketserver
import threading

import httpx
import pytest

from app import httpclient, mailer
from app.config import get_settings
from tests.conftest import audited
from tests.fakes import json_response

# conftest swaps mailer.send_magic_link for a recorder once the app starts; keep the real one.
send_magic_link = mailer.send_magic_link


class FakeSMTP(socketserver.StreamRequestHandler):
    """Just enough ESMTP: EHLO, AUTH XOAUTH2 or PLAIN, MAIL, RCPT, DATA, NOOP, QUIT."""
    accept_token = "good-token"
    received: list[dict] = []

    def reply(self, line: str):
        self.wfile.write((line + "\r\n").encode())

    def handle(self):
        self.reply("220 fake.smtp ready")
        session: dict = {"auth": None, "to": []}
        while True:
            raw = self.rfile.readline()
            if not raw:
                return
            cmd = raw.decode().rstrip("\r\n")
            verb = cmd.split(" ", 1)[0].upper()
            if verb in ("EHLO", "HELO"):
                self.reply("250-fake.smtp")
                self.reply("250 AUTH XOAUTH2 PLAIN")
            elif verb == "AUTH":
                _, mech, *rest = cmd.split(" ")
                decoded = base64.b64decode(rest[0]).decode() if rest else ""
                if mech == "XOAUTH2":
                    user, auth = decoded.split("\x01")[0], decoded.split("\x01")[1]
                    if auth == f"auth=Bearer {self.accept_token}":
                        session["auth"] = user
                        self.reply("235 2.7.0 Accepted")
                    else:
                        self.reply("334 " + base64.b64encode(b'{"status":"401"}').decode())
                        self.rfile.readline()  # the client's empty answer
                        self.reply("535 5.7.8 Username and Password not accepted")
                else:
                    session["auth"] = decoded.split("\x00")[1]
                    self.reply("235 2.7.0 Accepted")
            elif verb == "MAIL":
                self.reply("250 OK" if session["auth"] else "530 Authentication required")
            elif verb == "RCPT":
                session["to"].append(cmd)
                self.reply("250 OK")
            elif verb == "DATA":
                self.reply("354 go ahead")
                body = b""
                while (line := self.rfile.readline()) != b".\r\n":
                    body += line
                FakeSMTP.received.append({"user": session["auth"], "body": body.decode()})
                self.reply("250 OK queued")
            elif verb == "NOOP":
                self.reply("250 OK")
            elif verb == "QUIT":
                self.reply("221 bye")
                return
            else:
                self.reply("502 not implemented")


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.received = []
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), FakeSMTP)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    s = get_settings()
    for k, v in {"smtp_host": "127.0.0.1", "smtp_port": server.server_address[1], "smtp_starttls": False,
                 "smtp_user": "groundwork@contxtyfy.com", "mail_from": "groundwork@contxtyfy.com",
                 "smtp_auth": "xoauth2", "smtp_oauth_client_id": "cid", "smtp_oauth_client_secret": "csecret",
                 "smtp_oauth_refresh_token": "rtoken"}.items():
        monkeypatch.setattr(s, k, v)
    token_calls = []

    def token_endpoint(request: httpx.Request):
        form = dict(x.split("=", 1) for x in request.read().decode().split("&"))
        token_calls.append(form)
        return json_response({"access_token": "good-token", "expires_in": 3599, "token_type": "Bearer"})

    monkeypatch.setitem(httpclient.TRANSPORTS, "oauth", httpx.MockTransport(token_endpoint))
    mailer._token.update(value="", expires=0.0)
    yield token_calls
    server.shutdown()
    server.server_close()
    mailer._token.update(value="", expires=0.0)


def test_xoauth2_sends_with_a_refreshed_token_and_caches_it(smtp):
    send_magic_link("ryan@contxtyfy.com", "http://localhost:5173/auth/verify?token=abc")
    send_magic_link("ryan@contxtyfy.com", "http://localhost:5173/auth/verify?token=def")
    assert len(FakeSMTP.received) == 2 and FakeSMTP.received[0]["user"] == "user=groundwork@contxtyfy.com"
    msg = email.message_from_string(FakeSMTP.received[0]["body"], policy=email.policy.default)
    assert "token=abc" in msg.get_content() and msg["Subject"] == "Your sign-in link for Groundwork"
    assert len(smtp) == 1  # the access token was reused, not fetched twice
    assert smtp[0]["grant_type"] == "refresh_token" and smtp[0]["refresh_token"] == "rtoken"
    assert mailer.xoauth2_string("a@b", "t") == "user=a@b\x01auth=Bearer t\x01\x01"
    assert "signed in (xoauth2)" in mailer.check()


def test_a_refused_token_is_a_clear_error_and_is_dropped(smtp):
    FakeSMTP.accept_token = "something-else"
    try:
        with pytest.raises(mailer.MailError, match="refused the sign-in"):
            send_magic_link("ryan@contxtyfy.com", "http://x/auth/verify?token=abc")
        assert mailer._token["value"] == ""  # fetched again next time
    finally:
        FakeSMTP.accept_token = "good-token"


def test_password_sign_in_still_works(smtp, monkeypatch):
    monkeypatch.setattr(get_settings(), "smtp_auth", "password")
    monkeypatch.setattr(get_settings(), "smtp_password", "app-password")
    send_magic_link("ryan@contxtyfy.com", "http://x/auth/verify?token=abc")
    assert FakeSMTP.received[-1]["user"] == "groundwork@contxtyfy.com" and smtp == []


def test_a_failed_email_gets_a_clear_reply(client, monkeypatch):
    from app.routers import auth as auth_router

    def broken(to, link):
        raise mailer.MailError("Couldn't send email (ConnectionRefusedError).")

    monkeypatch.setattr(auth_router, "send_magic_link", broken)
    auth_router._hits.clear()
    r = client.post("/api/auth/request", json={"email": "someone@example.com.au"})
    assert r.status_code == 503 and "couldn't send the sign-in email" in r.json()["detail"]
    assert audited("auth.link_not_sent") >= 1
    assert "token" not in json.dumps(r.json())
