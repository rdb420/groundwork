"""Sign-in emails over SMTP.

Two ways to sign in to the mail server (GW_SMTP_AUTH):
- password: a username and password (for Gmail, an app password), or none for a local relay.
- xoauth2: OAuth 2.0 (SASL XOAUTH2), the way Google recommends for Gmail and Google Workspace. A
  refresh token (from scripts/gmail_oauth.py) is exchanged for a short-lived access token, which is
  cached until shortly before it expires.

TLS is always verified against the system's certificate store: STARTTLS on port 587, or TLS from
the first byte on port 465. Sign-in links and tokens are never logged.
"""
import logging
import smtplib
import ssl
import time
from email.message import EmailMessage

import httpx

from . import httpclient
from .config import get_settings

log = logging.getLogger("groundwork.mail")
_token: dict[str, float | str] = {"value": "", "expires": 0.0}


class MailError(RuntimeError):
    pass


def access_token() -> str:
    """A current OAuth access token for the mail account, refreshed when it's nearly expired."""
    if _token["value"] and float(_token["expires"]) > time.time() + 60:
        return str(_token["value"])
    s = get_settings()
    if not (s.smtp_oauth_client_id and s.smtp_oauth_client_secret and s.smtp_oauth_refresh_token):
        raise MailError("GW_SMTP_AUTH=xoauth2 needs GW_SMTP_OAUTH_CLIENT_ID, _CLIENT_SECRET and _REFRESH_TOKEN. "
                        "Run scripts/gmail_oauth.py.")
    try:
        with httpclient.client("oauth", timeout=15) as http:
            r = http.post(s.smtp_oauth_token_url, data={
                "client_id": s.smtp_oauth_client_id, "client_secret": s.smtp_oauth_client_secret,
                "refresh_token": s.smtp_oauth_refresh_token, "grant_type": "refresh_token"})
        if r.status_code != 200:
            reason = (r.json().get("error") if r.headers.get("content-type", "").startswith("application/json") else "")
            raise MailError(f"The mail account's OAuth token couldn't be refreshed ({r.status_code} {reason}). "
                            "Run scripts/gmail_oauth.py again.")
        body = r.json()
        _token["value"], _token["expires"] = body["access_token"], time.time() + float(body.get("expires_in", 3600))
        return str(_token["value"])
    except MailError:
        raise
    except httpx.HTTPError as e:
        raise MailError(f"Couldn't refresh the mail account's OAuth token ({type(e).__name__}).") from e
    except (KeyError, TypeError, ValueError) as e:
        raise MailError("The mail account's OAuth token response was in an unexpected shape. "
                        "Run scripts/gmail_oauth.py again.") from e


def xoauth2_string(user: str, token: str) -> str:
    """The SASL XOAUTH2 initial response (smtplib base64-encodes it)."""
    return f"user={user}\x01auth=Bearer {token}\x01\x01"


def _connect() -> smtplib.SMTP:
    s = get_settings()
    context = ssl.create_default_context()
    if s.smtp_port == 465:
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=15, context=context)
    else:
        smtp = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15)
        if s.smtp_starttls:
            smtp.starttls(context=context)
    smtp.ehlo()
    if s.smtp_auth == "xoauth2":
        token = access_token()
        initial = xoauth2_string(s.smtp_user, token)
        # On failure Google sends a base64 JSON error as a challenge; answering with an empty line
        # ends the exchange so smtplib raises SMTPAuthenticationError with the real code.
        smtp.auth("XOAUTH2", lambda challenge=None: initial if challenge is None else "", initial_response_ok=True)
    elif s.smtp_user:
        smtp.login(s.smtp_user, s.smtp_password)
    return smtp


def check() -> str:
    """Connect and sign in without sending anything. Returns the server's greeting name."""
    try:
        with _connect() as smtp:
            code, _ = smtp.noop()
            return f"{get_settings().smtp_host} signed in ({get_settings().smtp_auth}), NOOP {code}"
    except smtplib.SMTPAuthenticationError as e:
        _token["value"] = ""
        raise MailError(f"The mail server refused the sign-in ({e.smtp_code}).") from e
    except (smtplib.SMTPException, OSError) as e:
        raise MailError(f"Couldn't reach the mail server ({type(e).__name__}).") from e


def send(msg: EmailMessage) -> None:
    try:
        with _connect() as smtp:
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        _token["value"] = ""  # a revoked or stale token: fetch a new one next time
        raise MailError(f"The mail server refused the sign-in ({e.smtp_code}).") from e
    except (smtplib.SMTPException, OSError) as e:
        raise MailError(f"Couldn't send email ({type(e).__name__}).") from e


def send_magic_link(to: str, link: str) -> None:
    s = get_settings()
    subject = f"Your sign-in link for {s.app_name}"
    body = (
        f"Hi,\n\nUse this link to sign in to {s.app_name}, the {s.org_name} knowledge portal:\n\n{link}\n\n"
        f"It works once and expires in {s.magic_link_minutes} minutes. "
        "If you didn't ask for it, you can ignore this email.\n"
    )
    if not s.smtp_host:
        if s.dev_log_magic_links:
            log.warning("SMTP not configured. Magic link for %s: %s", to, link)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.mail_from, to, subject
    msg.set_content(body)
    send(msg)
