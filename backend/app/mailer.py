import logging
import smtplib
from email.message import EmailMessage

from .config import get_settings

log = logging.getLogger("groundwork.mail")


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
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
        if s.smtp_starttls:
            smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(msg)
