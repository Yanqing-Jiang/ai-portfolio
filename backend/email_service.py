"""
Gmail API integration for booking confirmation emails.

Function: send_booking_confirmation_email — sends an HTML confirmation email
to the client after a successful booking, including the Google Meet link and
reschedule/cancel instructions.

Called from: backend.main (booking webhook)
Invokes: Gmail API via OAuth 2.0 user credentials (refresh-token flow).
Reuses: ~/.gmail-mcp/credentials.json (authorized user info format).
Design: fire-and-forget. Errors are logged but never raise — webhook returns 200 regardless.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GMAIL_FROM_EMAIL = os.getenv("GMAIL_FROM_EMAIL", "")
GMAIL_CREDENTIALS_PATH = os.getenv(
    "GMAIL_CREDENTIALS_PATH", "~/.gmail-mcp/credentials.json"
)
BOOKING_TIMEZONE = os.getenv("BOOKING_TIMEZONE", "America/Los_Angeles")
# Admin alert recipient for new bookings. If empty, the admin alert is skipped.
ADMIN_ALERT_EMAIL = os.getenv("ADMIN_ALERT_EMAIL", "jiangyanqing90@gmail.com")

# Scopes must match the ones the stored token was granted for.
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.settings.basic",
]

# ---------------------------------------------------------------------------
# Gmail client (lazy-init, OAuth user-token flow)
# ---------------------------------------------------------------------------

_gmail_service = None
_gmail_configured = False


def _load_credentials_path() -> Optional[Path]:
    """Resolve the credentials path, expanding ~. Returns Path or None."""
    raw = GMAIL_CREDENTIALS_PATH or ""
    if not raw:
        return None
    p = Path(raw).expanduser()
    return p


def _get_gmail_service():
    """Lazy-initialize the Gmail API client using OAuth user credentials.

    The credentials file (~/.gmail-mcp/credentials.json) is in Google's
    "authorized user info" format (access_token, refresh_token, scope,
    token_type, expiry_date). We load it with
    `Credentials.from_authorized_user_info()` and auto-refresh expired
    access tokens via google.auth.transport.requests.Request before building
    the service.
    """
    global _gmail_service, _gmail_configured

    if _gmail_service is not None:
        return _gmail_service

    creds_path = _load_credentials_path()
    if not GMAIL_FROM_EMAIL or creds_path is None or not creds_path.exists():
        logger.warning(
            "[GMAIL] Gmail not configured — GMAIL_FROM_EMAIL or "
            "GMAIL_CREDENTIALS_PATH missing/invalid. Email sending disabled."
        )
        _gmail_configured = False
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        with open(creds_path, "r", encoding="utf-8") as fh:
            creds_info = json.load(fh)

        # OAuth user-token files from the gmail-mcp setup store only the
        # tokens (access/refresh); from_authorized_user_info() also needs
        # client_id + client_secret to refresh. Pull those from the sibling
        # gcp-oauth.keys.json when missing.
        if "client_id" not in creds_info or "client_secret" not in creds_info:
            keys_path = creds_path.parent / "gcp-oauth.keys.json"
            if keys_path.exists():
                with open(keys_path, "r", encoding="utf-8") as fh:
                    keys_info = json.load(fh)
                section = keys_info.get("installed") or keys_info.get("web") or {}
                creds_info.setdefault("client_id", section.get("client_id", ""))
                creds_info.setdefault(
                    "client_secret", section.get("client_secret", "")
                )
                creds_info.setdefault(
                    "token_uri",
                    section.get(
                        "token_uri", "https://oauth2.googleapis.com/token"
                    ),
                )

        credentials = Credentials.from_authorized_user_info(
            creds_info, scopes=GMAIL_SCOPES
        )

        # Auto-refresh if the access token is expired or missing.
        if credentials.expired or not credentials.token:
            credentials.refresh(Request())
            # Persist the refreshed token so the next process start has it.
            try:
                with open(creds_path, "w", encoding="utf-8") as fh:
                    json.dump(json.loads(credentials.to_json()), fh, indent=2)
            except Exception as write_exc:
                logger.warning(
                    "[GMAIL] Could not persist refreshed token: %s", write_exc
                )

        _gmail_service = build("gmail", "v1", credentials=credentials)
        _gmail_configured = True
        logger.info("[GMAIL] Gmail API client initialized (from=%s)", GMAIL_FROM_EMAIL)
        return _gmail_service

    except Exception as exc:
        logger.error("[GMAIL] Failed to initialize Gmail client: %s", exc)
        _gmail_configured = False
        return None


# ---------------------------------------------------------------------------
# Email body builder
# ---------------------------------------------------------------------------

def _build_email_html(
    name: str,
    session_type: str,
    slot_start_iso: str,
    meet_link: Optional[str],
) -> str:
    """Return an HTML email body with booking details, Meet link, and
    reschedule/cancel instructions."""
    duration = "60 minutes" if session_type == "60" else "30 minutes"

    # Format the slot start time for display (best-effort, tz-aware)
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        dt = datetime.fromisoformat(slot_start_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(BOOKING_TIMEZONE))
        pretty_time = dt.strftime("%A, %B %-d, %Y at %-I:%M %p %Z")
    except Exception:
        pretty_time = slot_start_iso

    meet_block = ""
    if meet_link:
        meet_block = f"""
        <tr>
          <td style="padding:8px 0;color:#5f6368;font-family:Arial,sans-serif;font-size:14px;">Google&nbsp;Meet</td>
          <td style="padding:8px 0;font-family:Arial,sans-serif;font-size:14px;">
            <a href="{meet_link}" style="color:#1a73e8;text-decoration:none;">{meet_link}</a>
          </td>
        </tr>"""
    else:
        meet_block = """
        <tr>
          <td style="padding:8px 0;color:#5f6368;font-family:Arial,sans-serif;font-size:14px;">Google&nbsp;Meet</td>
          <td style="padding:8px 0;font-family:Arial,sans-serif;font-size:14px;color:#5f6368;">
            Will be added shortly — you'll get a calendar invite with the link.
          </td>
        </tr>"""

    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background-color:#f8f9fa;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8f9fa;padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;max-width:560px;">
        <tr><td style="padding:32px 40px 0 40px;">
          <h1 style="margin:0 0 8px 0;font-family:Arial,sans-serif;font-size:22px;color:#202124;">Booking confirmed</h1>
          <p style="margin:0 0 24px 0;font-family:Arial,sans-serif;font-size:15px;color:#5f6368;">
            Hi {name},
          </p>
          <p style="margin:0 0 20px 0;font-family:Arial,sans-serif;font-size:15px;color:#202124;line-height:1.5;">
            Your consulting session is booked. Here are the details:
          </p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            <tr>
              <td style="padding:8px 0;color:#5f6368;font-family:Arial,sans-serif;font-size:14px;width:140px;vertical-align:top;">When</td>
              <td style="padding:8px 0;font-family:Arial,sans-serif;font-size:14px;color:#202124;">{pretty_time}</td>
            </tr>
            <tr>
              <td style="padding:8px 0;color:#5f6368;font-family:Arial,sans-serif;font-size:14px;">Duration</td>
              <td style="padding:8px 0;font-family:Arial,sans-serif;font-size:14px;color:#202124;">{duration}</td>
            </tr>
            {meet_block}
          </table>
          <p style="margin:24px 0 8px 0;font-family:Arial,sans-serif;font-size:14px;color:#202124;line-height:1.5;">
            <strong>Need to reschedule or cancel?</strong><br>
            Just reply to this email and I'll take care of it. No need to explain — simply let me know the new time you'd prefer, or that you'd like to cancel.
          </p>
        </td></tr>
        <tr><td style="padding:24px 40px 32px 40px;">
          <p style="margin:0;font-family:Arial,sans-serif;font-size:13px;color:#5f6368;line-height:1.5;">
            Talk soon,<br>
            Yanqing Jiang
          </p>
        </td></tr>
        <tr><td style="padding:0 40px 24px 40px;">
          <p style="margin:0;border-top:1px solid #e8eaed;padding-top:20px;font-family:Arial,sans-serif;font-size:12px;color:#9aa0a6;line-height:1.5;">
            This email was sent automatically when your booking was confirmed. If you didn't book a session, reply to let me know.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def send_booking_confirmation_email(
    name: str,
    email: str,
    session_type: str,
    slot_start: str,
    meet_link: Optional[str] = None,
) -> bool:
    """Send a booking confirmation email via Gmail API.

    Fire-and-forget design — returns True on success, False on failure or when
    Gmail is not configured. Never raises; errors are logged so the webhook is
    not blocked.

    Args:
        name: Client display name (used in greeting + subject).
        email: Client email address (recipient).
        session_type: "30" or "60".
        slot_start: ISO8601 string for the booked slot start.
        meet_link: Google Meet URL (may be None if calendar event creation
            succeeded without a Meet link or failed entirely).

    Returns:
        True if the email was sent, False otherwise.
    """
    service = _get_gmail_service()
    if service is None:
        logger.warning("[GMAIL] Skipping confirmation email — Gmail not configured")
        return False

    try:
        display_name = name or "there"
        duration = "60" if session_type == "60" else "30"
        subject = f"Booking confirmed — your {duration}-min session with Yanqing"

        html_body = _build_email_html(
            name=display_name,
            session_type=session_type,
            slot_start_iso=slot_start,
            meet_link=meet_link,
        )

        # Build the RFC822 message — MIMEMultipart("alternative") for HTML + plain
        mime_msg = MIMEMultipart("alternative")
        mime_msg["To"] = email
        mime_msg["From"] = (
            f"Yanqing Jiang <{GMAIL_FROM_EMAIL}>"
            if "@" in GMAIL_FROM_EMAIL
            else GMAIL_FROM_EMAIL
        )
        mime_msg["Subject"] = subject
        mime_msg["Reply-To"] = GMAIL_FROM_EMAIL

        # Plain-text fallback for clients that don't render HTML
        plain_text = (
            f"Booking confirmed\n\n"
            f"Hi {name or 'there'},\n\n"
            f"Your consulting session is booked.\n\n"
            f"When: {slot_start}\n"
            f"Duration: {duration} minutes\n"
        )
        if meet_link:
            plain_text += f"Google Meet: {meet_link}\n"
        plain_text += (
            "\nTo reschedule or cancel, just reply to this email.\n\n"
            "Talk soon,\nYanqing Jiang\n"
        )

        mime_msg.attach(MIMEText(plain_text, "plain", "utf-8"))
        mime_msg.attach(MIMEText(html_body, "html", "utf-8"))

        # Gmail API expects the raw message as urlsafe base64
        raw_message = base64.urlsafe_b64encode(
            mime_msg.as_bytes()
        ).decode("utf-8")

        # OAuth user token: userId="me" refers to the authenticated account.
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: service.users().messages().send(
                userId="me",
                body={"raw": raw_message},
            ).execute(),
        )

        logger.info("[GMAIL] Confirmation email sent to %s (session=%s)", email, session_type)
        return True

    except Exception as exc:
        # Fire-and-forget: log and return False, never raise
        logger.error("[GMAIL] Failed to send confirmation email to %s: %s", email, exc)
        return False


async def send_admin_booking_alert(
    name: str,
    email: str,
    session_type: str,
    slot_start: str,
    notes: Optional[str] = None,
    meet_link: Optional[str] = None,
) -> bool:
    """Email an internal alert to ADMIN_ALERT_EMAIL when a booking is confirmed.

    Reuses the same Gmail client as the client confirmation email. This is an
    INTERNAL notification — it includes the client's email and notes, so it is
    sent only to the admin address, never to the client. Fire-and-forget:
    returns True on success, False otherwise; never raises.
    """
    if not ADMIN_ALERT_EMAIL:
        return False

    service = _get_gmail_service()
    if service is None:
        logger.warning("[GMAIL] Skipping admin alert — Gmail not configured")
        return False

    try:
        duration = "60" if session_type == "60" else "30"
        subject = f"New consult booking — {name or 'unknown'} ({duration} min)"

        lines = [
            "New consult booking confirmed on yanqing.app/consult",
            "",
            f"Name:     {name or '(none)'}",
            f"Email:    {email or '(none)'}",
            f"Duration: {duration} minutes",
            f"When:     {slot_start}",
        ]
        if notes:
            lines.append(f"Notes:    {notes}")
        if meet_link:
            lines.append(f"Meet:     {meet_link}")
        plain_text = "\n".join(lines) + "\n"

        mime_msg = MIMEText(plain_text, "plain", "utf-8")
        mime_msg["To"] = ADMIN_ALERT_EMAIL
        mime_msg["From"] = (
            f"Yanqing Bookings <{GMAIL_FROM_EMAIL}>"
            if "@" in GMAIL_FROM_EMAIL
            else GMAIL_FROM_EMAIL
        )
        mime_msg["Subject"] = subject
        if email and "@" in email:
            mime_msg["Reply-To"] = email

        raw_message = base64.urlsafe_b64encode(
            mime_msg.as_bytes()
        ).decode("utf-8")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: service.users().messages().send(
                userId="me",
                body={"raw": raw_message},
            ).execute(),
        )

        logger.info("[GMAIL] Admin booking alert sent to %s", ADMIN_ALERT_EMAIL)
        return True

    except Exception as exc:
        logger.error("[GMAIL] Failed to send admin booking alert: %s", exc)
        return False