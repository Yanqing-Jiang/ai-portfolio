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
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from google_oauth import load_user_credentials, resolve_credentials_path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GMAIL_FROM_EMAIL = os.getenv("GMAIL_FROM_EMAIL", "")
GMAIL_CREDENTIALS_PATH = os.getenv(
    "GMAIL_CREDENTIALS_PATH", "~/.gmail-mcp/credentials.json"
)
BOOKING_TIMEZONE = os.getenv("BOOKING_TIMEZONE", "America/Los_Angeles")
# Admin alert recipient(s) for new bookings / consult intake. Comma-separated list.
# Every consult + context-form submission is copied to BOTH addresses (D5).
# If empty, the admin alert is skipped.
ADMIN_ALERT_EMAIL = os.getenv(
    "ADMIN_ALERT_EMAIL", "yanqing.app@gmail.com,jiangyanqing91@gmail.com"
)


def _admin_alert_recipients() -> list[str]:
    """Parse ADMIN_ALERT_EMAIL into a de-duplicated list of addresses."""
    seen: list[str] = []
    for part in (ADMIN_ALERT_EMAIL or "").split(","):
        addr = part.strip()
        if addr and addr not in seen:
            seen.append(addr)
    return seen

# What this module actually needs: it only calls messages.send. Requiring more
# (the stored token also carries gmail.settings.basic for gmail-mcp) would reject
# a token that can send perfectly well.
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
]

# ---------------------------------------------------------------------------
# Gmail client (lazy-init, OAuth user-token flow)
# ---------------------------------------------------------------------------

_gmail_service = None


def _get_gmail_service():
    """Lazy-initialize the Gmail API client using OAuth user credentials.

    Token loading, scope checking and refresh live in google_oauth, so Gmail and
    Calendar share one token file without drifting apart on how they read it.
    """
    global _gmail_service

    if _gmail_service is not None:
        return _gmail_service

    creds_path = resolve_credentials_path(GMAIL_CREDENTIALS_PATH or "")
    if not GMAIL_FROM_EMAIL or creds_path is None or not creds_path.exists():
        logger.warning(
            "[GMAIL] Gmail not configured — GMAIL_FROM_EMAIL or "
            "GMAIL_CREDENTIALS_PATH missing/invalid. Email sending disabled."
        )
        return None

    try:
        from googleapiclient.discovery import build

        credentials = load_user_credentials(
            creds_path, GMAIL_SCOPES, log_prefix="[GMAIL]"
        )
        if credentials is None:
            return None

        _gmail_service = build("gmail", "v1", credentials=credentials)
        logger.info("[GMAIL] Gmail API client initialized (from=%s)", GMAIL_FROM_EMAIL)
        return _gmail_service

    except Exception as exc:
        logger.error("[GMAIL] Failed to initialize Gmail client: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Email body builder
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# iCalendar (RFC 5545)
# ---------------------------------------------------------------------------

# The client's own calendar is the calendar: we don't own one, so we hand them a
# standards-compliant event they can add, and later move or withdraw. The UID is
# what makes that work — same UID + higher SEQUENCE moves the event, same UID with
# METHOD:CANCEL removes it. Keyed on the booking id, which is stable across a
# reschedule chain only if we pass the ORIGINAL id; see main.py's reschedule.
ICS_UID_DOMAIN = os.getenv("ICS_UID_DOMAIN", "yanqing.app")


def _ics_escape(value: str) -> str:
    """Escape per RFC 5545 §3.3.11 (order matters: backslash first)."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _ics_fold(line: str) -> str:
    """Fold to 75 octets with a leading space on continuations (RFC 5545 §3.1).

    Folds on OCTETS, not characters, and never splits a UTF-8 sequence — a naive
    75-character split corrupts multi-byte names.
    """
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    chunks, start = [], 0
    while start < len(raw):
        end = min(start + (75 if not chunks else 74), len(raw))
        # Back off until we're on a UTF-8 boundary.
        while end > start and end < len(raw) and (raw[end] & 0xC0) == 0x80:
            end -= 1
        chunks.append(raw[start:end].decode("utf-8"))
        start = end
    return "\r\n ".join(chunks)


def build_booking_ics(
    *,
    booking_id: str,
    slot_start_iso: str,
    session_type: str,
    client_name: str,
    client_email: str,
    meet_link: Optional[str] = None,
    cancelled: bool = False,
    sequence: int = 0,
) -> str:
    """Return an iCalendar VEVENT for a booking.

    `cancelled=True` emits METHOD:CANCEL, which withdraws the event the client
    already has. `sequence` must increase on every revision or clients ignore the
    update as stale.
    """
    from datetime import datetime, timedelta, timezone as _tz
    from zoneinfo import ZoneInfo

    dt = datetime.fromisoformat(slot_start_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(BOOKING_TIMEZONE))
    start_utc = dt.astimezone(_tz.utc)
    minutes = 60 if session_type == "60" else 30
    end_utc = start_utc + timedelta(minutes=minutes)

    def stamp(value: datetime) -> str:
        return value.strftime("%Y%m%dT%H%M%SZ")

    organizer = GMAIL_FROM_EMAIL or "yanqing.app@gmail.com"
    summary = f"Consulting session with Yanqing Jiang ({minutes} min)"
    description = (
        "Cancelled." if cancelled
        else (f"Join: {meet_link}" if meet_link
              else "Yanqing will email the video link before the call.")
    )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//yanqing.app//booking//EN",
        "CALSCALE:GREGORIAN",
        f"METHOD:{'CANCEL' if cancelled else 'REQUEST'}",
        "BEGIN:VEVENT",
        f"UID:{booking_id}@{ICS_UID_DOMAIN}",
        f"SEQUENCE:{sequence}",
        f"DTSTAMP:{stamp(datetime.now(_tz.utc))}",
        f"DTSTART:{stamp(start_utc)}",
        f"DTEND:{stamp(end_utc)}",
        f"SUMMARY:{_ics_escape(summary)}",
        f"DESCRIPTION:{_ics_escape(description)}",
        f"ORGANIZER;CN={_ics_escape('Yanqing Jiang')}:mailto:{organizer}",
        f"ATTENDEE;CN={_ics_escape(client_name or client_email)};ROLE=REQ-PARTICIPANT;"
        f"PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:{client_email}",
        f"STATUS:{'CANCELLED' if cancelled else 'CONFIRMED'}",
    ]
    if meet_link and not cancelled:
        lines.append(f"LOCATION:{_ics_escape(meet_link)}")
        lines.append(f"URL:{meet_link}")
    if not cancelled:
        lines += [
            "BEGIN:VALARM",
            "TRIGGER:-PT60M",
            "ACTION:DISPLAY",
            "DESCRIPTION:Consulting session in 1 hour",
            "END:VALARM",
        ]
    lines += ["END:VEVENT", "END:VCALENDAR"]

    # CRLF is mandatory, and a trailing CRLF keeps strict parsers happy.
    return "\r\n".join(_ics_fold(line) for line in lines) + "\r\n"


_EMAIL_COPY = {
    "confirmed": (
        "Booking confirmed",
        "Your consulting session is booked. Here are the details:",
    ),
    "rescheduled": (
        "Booking moved",
        "Your session has been moved. Here are the new details:",
    ),
    "cancelled": (
        "Booking cancelled",
        "Your session has been cancelled. Nothing further is needed:",
    ),
}


def _build_email_html(
    name: str,
    session_type: str,
    slot_start_iso: str,
    meet_link: Optional[str],
    notes: Optional[str] = None,
    kind: str = "confirmed",
) -> str:
    """Return an HTML email body with booking details, Meet link, the context
    the client shared, and reschedule/cancel instructions."""
    duration = "60 minutes" if session_type == "60" else "30 minutes"
    heading, lead = _EMAIL_COPY.get(kind, _EMAIL_COPY["confirmed"])
    if kind == "cancelled":
        meet_link = None  # nothing to join

    context_block = ""
    if notes and notes.strip():
        import html as _html
        safe_notes = _html.escape(notes.strip()).replace("\n", "<br>")
        context_block = f"""
          <p style="margin:24px 0 6px 0;font-family:Arial,sans-serif;font-size:14px;color:#202124;"><strong>What you shared</strong></p>
          <div style="font-family:Arial,sans-serif;font-size:13px;color:#5f6368;line-height:1.5;background:#f8f9fa;border-radius:6px;padding:12px 16px;">{safe_notes}</div>"""

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
    if kind == "cancelled":
        meet_block = ""
    elif meet_link:
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
            Yanqing will email you the link before the call.
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
          <h1 style="margin:0 0 8px 0;font-family:Arial,sans-serif;font-size:22px;color:#202124;">{heading}</h1>
          <p style="margin:0 0 24px 0;font-family:Arial,sans-serif;font-size:15px;color:#5f6368;">
            Hi {name},
          </p>
          <p style="margin:0 0 20px 0;font-family:Arial,sans-serif;font-size:15px;color:#202124;line-height:1.5;">
            {lead}
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
          {context_block}
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
    notes: Optional[str] = None,
    kind: str = "confirmed",
    booking_id: Optional[str] = None,
    ics_sequence: int = 0,
) -> bool:
    """Send a booking confirmation / move / cancellation email via Gmail API.

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
        subject_lead = {
            "confirmed": "Booking confirmed",
            "rescheduled": "Booking moved",
            "cancelled": "Booking cancelled",
        }.get(kind, "Booking confirmed")
        subject = f"{subject_lead} — your {duration}-min session with Yanqing"

        html_body = _build_email_html(
            name=display_name,
            session_type=session_type,
            slot_start_iso=slot_start,
            meet_link=meet_link,
            notes=notes,
            kind=kind,
        )

        # multipart/mixed so the calendar file rides alongside the alternative
        # plain/HTML pair. A bare "alternative" cannot carry an attachment.
        mime_msg = MIMEMultipart("mixed")
        body_part = MIMEMultipart("alternative")
        mime_msg["To"] = email
        mime_msg["From"] = (
            f"Yanqing Jiang <{GMAIL_FROM_EMAIL}>"
            if "@" in GMAIL_FROM_EMAIL
            else GMAIL_FROM_EMAIL
        )
        mime_msg["Subject"] = subject
        mime_msg["Reply-To"] = GMAIL_FROM_EMAIL

        # Plain-text fallback for clients that don't render HTML
        cancelled = kind == "cancelled"
        _, lead = _EMAIL_COPY.get(kind, _EMAIL_COPY["confirmed"])
        plain_text = (
            f"{subject_lead}\n\n"
            f"Hi {name or 'there'},\n\n"
            f"{lead}\n\n"
            f"When: {slot_start}\n"
            f"Duration: {duration} minutes\n"
        )
        if meet_link and not cancelled:
            plain_text += f"Google Meet: {meet_link}\n"
        # Only claim the attachment when one is actually going to be attached
        # (booking_id is what makes a correctable calendar entry possible).
        if booking_id and not cancelled:
            plain_text += "\nA calendar file is attached — add it and your calendar will remind you.\n"
        plain_text += (
            "\nTo reschedule or cancel, just reply to this email.\n\n"
            "Talk soon,\nYanqing Jiang\n"
        )

        body_part.attach(MIMEText(plain_text, "plain", "utf-8"))
        body_part.attach(MIMEText(html_body, "html", "utf-8"))
        mime_msg.attach(body_part)

        # The calendar part. Without a booking_id there is no stable UID, so a
        # later move/cancel could not refer to this event — send no file rather
        # than one we cannot correct.
        if booking_id:
            ics = build_booking_ics(
                booking_id=booking_id,
                slot_start_iso=slot_start,
                session_type=session_type,
                client_name=name or email,
                client_email=email,
                meet_link=meet_link,
                cancelled=cancelled,
                sequence=ics_sequence,
            )
            method = "CANCEL" if cancelled else "REQUEST"
            cal_part = MIMEText(ics, "calendar", "utf-8")
            cal_part.set_param("method", method)
            cal_part.set_param("name", "invite.ics")
            cal_part.add_header(
                "Content-Disposition", "attachment", filename="invite.ics"
            )
            mime_msg.attach(cal_part)

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

        logger.info(
            "[GMAIL] %s email sent to %s (session=%s ics=%s seq=%s)",
            kind, email, session_type, bool(booking_id), ics_sequence,
        )
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
    failure_reason: Optional[str] = None,
) -> bool:
    """Email an internal alert to ADMIN_ALERT_EMAIL when a booking is confirmed.

    Reuses the same Gmail client as the client confirmation email. This is an
    INTERNAL notification — it includes the client's email and notes, so it is
    sent only to the admin address, never to the client. Fire-and-forget:
    returns True on success, False otherwise; never raises.

    `failure_reason` flips this into a FAILED-ATTEMPT alert: someone reached the
    booking click and was turned away, which is worth knowing about immediately
    since nothing else records it.
    """
    recipients = _admin_alert_recipients()
    if not recipients:
        return False

    service = _get_gmail_service()
    if service is None:
        logger.warning("[GMAIL] Skipping admin alert — Gmail not configured")
        return False

    try:
        is_free = session_type == "fit"
        duration = "30" if is_free else ("60" if session_type == "60" else "30")
        kind = "Enterprise fit call (FREE)" if is_free else f"{duration}-min session"
        if failure_reason:
            subject = f"ACTION NEEDED — booking FAILED for {name or 'unknown'} ({kind})"
        elif not meet_link:
            subject = f"ACTION NEEDED — no Meet link for {name or 'unknown'} ({kind})"
        else:
            subject = f"New consult booking — {name or 'unknown'} ({kind})"

        lines = [
            "A booking attempt on yanqing.app/consult could NOT be confirmed."
            if failure_reason
            else "New consult booking confirmed on yanqing.app/consult",
            "",
            f"Type:     {kind}",
            f"Name:     {name or '(none)'}",
            f"Email:    {email or '(none)'}",
            f"Duration: {duration} minutes",
            f"When:     {slot_start}",
        ]
        if notes:
            lines.append(f"Notes:    {notes}")
        if meet_link:
            lines.append(f"Meet:     {meet_link}")
        elif not failure_reason:
            # The booking stands but the Meet room never provisioned, and nothing
            # retries it. The confirmation email tells them YOU will send the
            # link, so this is the only thing that makes that true.
            lines += [
                "Meet:     NONE — the room failed to provision.",
                "",
                "ACTION: add a Meet link to the event and email it to them. Their",
                "confirmation says you will send it before the call.",
            ]
        if failure_reason:
            lines += [
                "",
                f"Reason:   {failure_reason}",
                "",
                "They were shown an error and are NOT booked. Reach out directly",
                "if you want to save this one.",
            ]
        plain_text = "\n".join(lines) + "\n"

        mime_msg = MIMEText(plain_text, "plain", "utf-8")
        mime_msg["To"] = ", ".join(recipients)
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

        logger.info("[GMAIL] Admin booking alert sent to %s", ", ".join(recipients))
        return True

    except Exception as exc:
        logger.error("[GMAIL] Failed to send admin booking alert: %s", exc)
        return False