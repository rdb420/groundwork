"""Get the OAuth refresh token Groundwork uses to send sign-in emails through Gmail (Google
Workspace), once. Groundwork then signs in to smtp.gmail.com with SASL XOAUTH2.

Before you start, in Google Cloud console for the contxtyfy.com Workspace:
  1. APIs & Services > OAuth consent screen: User type "Internal", add the scope
     https://mail.google.com/ (Internal apps need no Google review).
  2. Credentials > Create credentials > OAuth client ID > Application type "Desktop app".
  3. Put its client ID and secret in .env as GW_SMTP_OAUTH_CLIENT_ID and GW_SMTP_OAUTH_CLIENT_SECRET,
     and set GW_SMTP_USER to the mailbox that sends (for example groundwork@contxtyfy.com).

Then, from backend/:
    uv run python -m scripts.gmail_oauth url
        Open the printed link, signed in as GW_SMTP_USER, and allow access. Google then sends the
        browser to http://127.0.0.1:8765/?code=... . That page won't load unless the browser is on
        this machine; that's fine. Copy the whole address from the address bar.
    uv run python -m scripts.gmail_oauth exchange '<the address you copied>'
        Swaps the code for a refresh token and saves it in ../.env as GW_SMTP_OAUTH_REFRESH_TOKEN.

The token grants sending (and reading) mail as that mailbox, so .env stays out of git and off
shared drives. Revoke it any time at https://myaccount.google.com/permissions.
"""
import base64
import hashlib
import json
import secrets
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

from app.config import get_settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
SCOPE = "https://mail.google.com/"
REDIRECT = "http://127.0.0.1:8765"
ENV = Path(__file__).resolve().parents[2] / ".env"


def _state_file() -> Path:
    return get_settings().data_dir / ".gmail_oauth_pending.json"


def url() -> None:
    s = get_settings()
    if not s.smtp_oauth_client_id:
        raise SystemExit("Set GW_SMTP_OAUTH_CLIENT_ID and GW_SMTP_OAUTH_CLIENT_SECRET in .env first.")
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    _state_file().write_text(json.dumps({"verifier": verifier, "state": state}))
    _state_file().chmod(0o600)
    params = {"client_id": s.smtp_oauth_client_id, "redirect_uri": REDIRECT, "response_type": "code",
              "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state,
              "code_challenge": challenge, "code_challenge_method": "S256"}
    if s.smtp_user:
        params["login_hint"] = s.smtp_user
    print("Open this link, signed in as", s.smtp_user or "the sending mailbox", "and allow access:\n")
    print(f"{AUTH_URL}?{urlencode(params)}\n")
    print("Then copy the address the browser ends up on and run:\n"
          "  uv run python -m scripts.gmail_oauth exchange '<address>'")


def _save(key: str, value: str) -> None:
    lines = ENV.read_text().splitlines() if ENV.exists() else []
    out, done = [], False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{key}={value}")
    ENV.write_text("\n".join(out) + "\n")


def exchange(address: str) -> None:
    s = get_settings()
    pending = json.loads(_state_file().read_text()) if _state_file().exists() else None
    if not pending:
        raise SystemExit("Run `url` first.")
    query = parse_qs(urlsplit(address).query) if "?" in address else {"code": [address]}
    if "error" in query:
        raise SystemExit(f"Google said: {query['error'][0]}")
    if "state" in query and query["state"][0] != pending["state"]:
        raise SystemExit("That address is from a different attempt. Run `url` again.")
    r = httpx.post(s.smtp_oauth_token_url, timeout=20, data={
        "code": query["code"][0], "client_id": s.smtp_oauth_client_id, "client_secret": s.smtp_oauth_client_secret,
        "redirect_uri": REDIRECT, "grant_type": "authorization_code", "code_verifier": pending["verifier"]})
    if r.status_code != 200:
        raise SystemExit(f"Google refused the code ({r.status_code} {r.json().get('error', '')}). Run `url` again.")
    token = r.json().get("refresh_token")
    if not token:
        raise SystemExit("Google sent no refresh token. Remove the app at https://myaccount.google.com/permissions "
                         "and run `url` again.")
    _save("GW_SMTP_OAUTH_REFRESH_TOKEN", token)
    _state_file().unlink()
    print(f"Saved GW_SMTP_OAUTH_REFRESH_TOKEN in {ENV}. Restart the API, then check it with "
          "`uv run python -m scripts.check_providers`.")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "url":
        url()
    elif len(sys.argv) >= 3 and sys.argv[1] == "exchange":
        exchange(sys.argv[2])
    else:
        raise SystemExit(__doc__)
