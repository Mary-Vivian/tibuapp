import json
import logging
import os
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)


def send_email(to, subject, text):
    """Send through Brevo's HTTP API (SMTP is blocked on Render's free plan)."""
    key = os.environ.get("BREVO_API_KEY")
    if not key or not settings.EMAIL_FROM:
        if settings.DEBUG:  # local testing: show the email in the terminal
            print(f"\n--- EMAIL to {to} ---\n{subject}\n{text}\n---------------\n")
        else:
            log.error("Email not configured: set BREVO_API_KEY and EMAIL_FROM")
        return False

    payload = {
        "sender": {"name": "Tibu Health", "email": settings.EMAIL_FROM},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": text,
    }
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode(),
        headers={"api-key": key, "content-type": "application/json", "accept": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        log.exception("Sending email failed")
        return False