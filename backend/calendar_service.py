"""
Google Calendar API integration for booking system.

Function: get_available_slots — queries Google Calendar freebusy API for available slots.
Function: create_booking_event — creates a calendar event with Google Meet link.
Called from: backend.main (booking endpoints)
Invokes: Google Calendar API via service account credentials.
Purpose: Manage consulting session availability and booking confirmation.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BOOKING_TIMEZONE = os.getenv("BOOKING_TIMEZONE", "America/Los_Angeles")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# Business hours (in BOOKING_TIMEZONE)
# Weekday (Mon-Fri): 1pm-5pm PT | Weekend (Sat-Sun): 1pm-4:30pm PT
WEEKDAY_HOUR_START = 13   # 1 PM
WEEKDAY_HOUR_END = 17     # 5 PM
WEEKEND_HOUR_START = 13   # 1 PM
WEEKEND_HOUR_END_H = 16   # 4:30 PM (hour component)
WEEKEND_HOUR_END_M = 30   # 4:30 PM (minute component)
BUFFER_MINUTES = 15       # buffer between sessions
SLOT_DURATION_MINUTES = 30  # base slot size

# Session durations
SESSION_DURATIONS = {
    "30": 30,
    "60": 60,
}

# ---------------------------------------------------------------------------
# Google Calendar client (lazy-init)
# ---------------------------------------------------------------------------

_calendar_service = None
_calendar_configured = False


def _get_calendar_service():
    """Lazy-initialize the Google Calendar API client using service account credentials."""
    global _calendar_service, _calendar_configured

    if _calendar_service is not None:
        return _calendar_service

    if not GOOGLE_SERVICE_ACCOUNT_JSON or not GOOGLE_CALENDAR_ID:
        logger.warning(
            "[CALENDAR] Google Calendar not configured — "
            "GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_CALENDAR_ID missing. "
            "Using mock mode."
        )
        _calendar_configured = False
        return None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_json = base64.b64decode(GOOGLE_SERVICE_ACCOUNT_JSON)
        creds_info = json.loads(creds_json)

        credentials = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=[
                "https://www.googleapis.com/auth/calendar.readonly",
                "https://www.googleapis.com/auth/calendar.events",
            ],
        )

        _calendar_service = build("calendar", "v3", credentials=credentials)
        _calendar_configured = True
        logger.info("[CALENDAR] Google Calendar API client initialized")
        return _calendar_service

    except Exception as exc:
        logger.error("[CALENDAR] Failed to initialize Google Calendar client: %s", exc)
        _calendar_configured = False
        return None


# ---------------------------------------------------------------------------
# Slot generation helpers
# ---------------------------------------------------------------------------

def _generate_slot_boundaries(target_date: date, tz: ZoneInfo) -> list[tuple[datetime, datetime]]:
    """Generate all possible 30-minute slot boundaries within business hours for a given date.

    Returns a list of (start, end) tuples in the configured timezone.
    Mon-Fri: 1pm-5pm PT | Sat-Sun: 1pm-4:30pm PT.
    """
    is_weekend = target_date.weekday() >= 5  # 5=Sat, 6=Sun

    if is_weekend:
        hour_start, min_start = WEEKEND_HOUR_START, 0
        hour_end, min_end = WEEKEND_HOUR_END_H, WEEKEND_HOUR_END_M
    else:
        hour_start, min_start = WEEKDAY_HOUR_START, 0
        hour_end, min_end = WEEKDAY_HOUR_END, 0

    slots = []
    start_of_day = datetime(
        target_date.year, target_date.month, target_date.day,
        hour_start, min_start, 0,
        tzinfo=tz,
    )
    end_of_day = datetime(
        target_date.year, target_date.month, target_date.day,
        hour_end, min_end, 0,
        tzinfo=tz,
    )

    current = start_of_day
    while current + timedelta(minutes=SLOT_DURATION_MINUTES) <= end_of_day:
        slot_end = current + timedelta(minutes=SLOT_DURATION_MINUTES)
        slots.append((current, slot_end))
        current = slot_end

    return slots


def _overlaps(busy_start: datetime, busy_end: datetime, slot_start: datetime, slot_end: datetime) -> bool:
    """Check if a busy period overlaps with a slot (including buffer)."""
    # Add buffer: the slot effectively blocks slot_start to slot_end + BUFFER_MINUTES
    buffered_end = slot_end + timedelta(minutes=BUFFER_MINUTES)
    return busy_start < buffered_end and busy_end > slot_start


# ---------------------------------------------------------------------------
# Mock data for development without Google credentials
# ---------------------------------------------------------------------------

def _mock_available_slots(target_date: date, session_type: str = "30") -> list[dict]:
    """Return all slots as available (no Google Calendar to check against).

    The DB layer in main.py still filters out held/confirmed bookings.
    """
    tz = ZoneInfo(BOOKING_TIMEZONE)
    all_slots = _generate_slot_boundaries(target_date, tz)
    duration = SESSION_DURATIONS.get(session_type, 30)

    if not all_slots:
        return []

    available = []
    if duration == 60:
        # 60-min: need two consecutive free slots
        for i, (start, _end) in enumerate(all_slots):
            if i + 1 < len(all_slots):
                mock_end = start + timedelta(minutes=60)
                available.append({
                    "start": start.isoformat(),
                    "end": mock_end.isoformat(),
                })
    else:
        for start, end in all_slots:
            available.append({
                "start": start.isoformat(),
                "end": end.isoformat(),
            })

    return available


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_available_slots(target_date: date, session_type: str = "30") -> list[dict]:
    """Query Google Calendar freebusy API, return available slot boundaries.

    Business hours: 9AM-5PM in BOOKING_TIMEZONE. Mon-Fri only.
    Excludes busy slots. Adds 15-min buffer between sessions.
    For 60-min sessions: only return slots where the next slot is also free.

    Returns: [{"start": "ISO8601 with offset", "end": "ISO8601 with offset"}]
    """
    tz = ZoneInfo(BOOKING_TIMEZONE)
    duration = SESSION_DURATIONS.get(session_type, 30)

    service = _get_calendar_service()
    if service is None:
        logger.info("[CALENDAR] Using mock slots (Google Calendar not configured)")
        return _mock_available_slots(target_date, session_type)

    all_slots = _generate_slot_boundaries(target_date, tz)
    if not all_slots:
        return []

    # Query freebusy for the entire business day
    time_min = all_slots[0][0].isoformat()
    time_max = (all_slots[-1][1] + timedelta(minutes=BUFFER_MINUTES)).isoformat()

    try:
        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "timeZone": BOOKING_TIMEZONE,
            "items": [{"id": GOOGLE_CALENDAR_ID}],
        }

        # Google API client is synchronous — call in thread
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: service.freebusy().query(body=body).execute(),
        )

        busy_periods = result.get("calendars", {}).get(GOOGLE_CALENDAR_ID, {}).get("busy", [])

        # Parse busy periods into timezone-aware datetimes
        busy_ranges = []
        for period in busy_periods:
            busy_start = datetime.fromisoformat(period["start"])
            busy_end = datetime.fromisoformat(period["end"])
            busy_ranges.append((busy_start, busy_end))

    except Exception as exc:
        logger.error("[CALENDAR] Freebusy query failed: %s", exc)
        # Graceful degradation: return all slots as available rather than failing
        # The Supabase check in main.py will still filter holds/confirmed bookings
        busy_ranges = []

    # Filter out slots that overlap with busy periods (including buffer)
    free_slot_indices: list[int] = []
    for i, (slot_start, slot_end) in enumerate(all_slots):
        is_free = True
        for busy_start, busy_end in busy_ranges:
            if _overlaps(busy_start, busy_end, slot_start, slot_end):
                is_free = False
                break
        if is_free:
            free_slot_indices.append(i)

    free_set = set(free_slot_indices)

    available = []
    if duration == 60:
        # 60-min: need two consecutive free slots
        for i in free_slot_indices:
            if (i + 1) in free_set:
                start = all_slots[i][0]
                end = start + timedelta(minutes=60)
                available.append({
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                })
    else:
        # 30-min: each free slot is available
        for i in free_slot_indices:
            start, end = all_slots[i]
            available.append({
                "start": start.isoformat(),
                "end": end.isoformat(),
            })

    return available


async def create_booking_event(
    session_type: str,
    slot_start: datetime,
    name: str,
    email: str,
    notes: str | None = None,
) -> dict:
    """Create a Google Calendar event with Google Meet link.

    Uses conferenceDataVersion=1 and conferenceData.createRequest for Meet link.
    Adds client email as attendee (Google auto-sends invite).

    Returns: {"event_id": str, "meet_link": str}
    Raises: RuntimeError if calendar is not configured or creation fails.
    """
    tz = ZoneInfo(BOOKING_TIMEZONE)
    duration = SESSION_DURATIONS.get(session_type, 30)
    slot_end = slot_start + timedelta(minutes=duration)

    service = _get_calendar_service()
    if service is None:
        logger.warning("[CALENDAR] Cannot create event — Google Calendar not configured")
        raise RuntimeError("Google Calendar not configured")

    description_parts = [
        f"Consulting session with {name} ({email})",
        f"Session type: {duration} minutes",
    ]
    if notes:
        description_parts.append(f"\nClient notes:\n{notes}")

    event_body = {
        "summary": f"Consulting: {name} ({duration}min)",
        "description": "\n".join(description_parts),
        "start": {
            "dateTime": slot_start.isoformat(),
            "timeZone": BOOKING_TIMEZONE,
        },
        "end": {
            "dateTime": slot_end.isoformat(),
            "timeZone": BOOKING_TIMEZONE,
        },
        "attendees": [
            {"email": email},
        ],
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {
                    "type": "hangoutsMeet",
                },
            },
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 60},
                {"method": "popup", "minutes": 15},
            ],
        },
    }

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        created_event = await loop.run_in_executor(
            None,
            lambda: service.events().insert(
                calendarId=GOOGLE_CALENDAR_ID,
                body=event_body,
                conferenceDataVersion=1,
                sendUpdates="all",  # sends invite to attendees
            ).execute(),
        )

        event_id = created_event.get("id", "")
        meet_link = ""

        # Extract Meet link from conference data
        conference_data = created_event.get("conferenceData", {})
        entry_points = conference_data.get("entryPoints", [])
        for ep in entry_points:
            if ep.get("entryPointType") == "video":
                meet_link = ep.get("uri", "")
                break

        logger.info(
            "[CALENDAR] Event created: id=%s meet=%s for %s",
            event_id, bool(meet_link), email,
        )

        return {"event_id": event_id, "meet_link": meet_link}

    except Exception as exc:
        logger.error("[CALENDAR] Event creation failed: %s", exc)
        raise RuntimeError(f"Calendar event creation failed: {exc}") from exc


async def delete_booking_event(calendar_event_id: str) -> bool:
    """Delete a Google Calendar event (used for cancel/reschedule).

    Sends cancellation notifications to all attendees.
    Returns True on success.
    Raises RuntimeError if calendar is not configured or deletion fails.
    """
    service = _get_calendar_service()
    if service is None:
        raise RuntimeError("Google Calendar not configured")

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: service.events().delete(
                calendarId=GOOGLE_CALENDAR_ID,
                eventId=calendar_event_id,
                sendUpdates="all",
            ).execute(),
        )
        logger.info("[CALENDAR] Event deleted: %s", calendar_event_id)
        return True
    except Exception as exc:
        logger.error("[CALENDAR] Event deletion failed: %s", exc)
        raise RuntimeError(f"Calendar event deletion failed: {exc}") from exc
