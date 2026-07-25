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
import hashlib
import json
import logging
import os
import random
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
# Weekday (Mon-Fri): 8am-4pm PT, but only a few staggered windows are offered
# (see _weekday_stagger) | Weekend (Sat-Sun): 1pm-4pm PT, fully open.
WEEKDAY_HOUR_START = 8    # 8 AM
WEEKDAY_HOUR_END = 16     # 4 PM
WEEKEND_HOUR_START = 13   # 1 PM
WEEKEND_HOUR_END_H = 16   # 4 PM (hour component)
WEEKEND_HOUR_END_M = 0    # 4 PM (minute component)
BUFFER_MINUTES = 15       # buffer between sessions
SLOT_DURATION_MINUTES = 30  # base slot size

# Weekday stagger: how much of the 8am-4pm grid to actually publish.
WEEKDAY_OPEN_WINDOWS = 3    # contiguous windows offered per weekday
WEEKDAY_WINDOW_SLOTS = 2    # 30-min slots per window (2 => a bookable 60-min pair)
# Changing the salt reshuffles every future weekday. Keep it stable in prod.
SLOT_STAGGER_SALT = os.getenv("BOOKING_SLOT_SALT", "yj-booking-v1")

# Meet rooms are sometimes provisioned asynchronously; re-read the event until
# the link appears (total worst case ~6s) before giving up on it.
MEET_POLL_ATTEMPTS = 3
MEET_POLL_DELAY_S = 1.0

# Workspace domain-wide delegation: the service account acts AS this user, which
# is what lets Google email the invitation to an external attendee. Left empty,
# the service account books as itself and attendee invites are unreliable.
GOOGLE_CALENDAR_IMPERSONATE_USER = os.getenv("GOOGLE_CALENDAR_IMPERSONATE_USER", "")

# Don't publish a slot that starts within this many minutes — weekday hours now
# open at 8am, so without a lead time the afternoon visitor is shown morning
# slots that the booking endpoint would reject as being in the past.
MIN_LEAD_MINUTES = 30

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

        if GOOGLE_CALENDAR_IMPERSONATE_USER:
            credentials = credentials.with_subject(GOOGLE_CALENDAR_IMPERSONATE_USER)
            logger.info(
                "[CALENDAR] Impersonating %s (domain-wide delegation)",
                GOOGLE_CALENDAR_IMPERSONATE_USER,
            )
        else:
            logger.warning(
                "[CALENDAR] GOOGLE_CALENDAR_IMPERSONATE_USER not set — the service "
                "account books as itself; Google may not email the invitation to "
                "the attendee. Set it to the calendar owner for reliable invites."
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

def _stagger_rng(target_date: date) -> random.Random:
    """A PRNG seeded only by the date, so the same day always staggers the same way.

    Uses sha256 rather than hash() — str hashing is salted per process, which
    would give each backend worker (and each restart) a different day.
    """
    digest = hashlib.sha256(f"{SLOT_STAGGER_SALT}:{target_date.isoformat()}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _weekday_stagger(
    target_date: date,
    slots: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    """Publish only a few windows of the weekday grid, in date-dependent positions.

    Mon-Fri spans a whole workday (8am-4pm = 16 slots); offering all of it reads
    as a calendar with nothing in it. Instead open WEEKDAY_OPEN_WINDOWS contiguous
    windows, each WEEKDAY_WINDOW_SLOTS long, placed by _stagger_rng — so the day
    looks partly taken and the open times move from day to day. Windows stay
    contiguous so a 60-min session still has consecutive free slots to land on.

    Deterministic by necessity, not convenience: this function is also the
    revalidation source for booking (main._assert_slot_offered), so a given date
    must always produce the same offer. A live random.random() would reject the
    very slot it had just advertised.
    """
    n_buckets = WEEKDAY_OPEN_WINDOWS + 1  # one bucket stays dark, and which one moves
    # Each bucket needs room for its window plus a closing slot (see below).
    if len(slots) < n_buckets * (WEEKDAY_WINDOW_SLOTS + 1):
        return slots  # too short to thin out — offer it whole

    edges = [round(i * len(slots) / n_buckets) for i in range(n_buckets + 1)]
    rng = _stagger_rng(target_date)
    keep: set[int] = set()
    for bucket in rng.sample(range(n_buckets), WEEKDAY_OPEN_WINDOWS):
        lo, hi = edges[bucket], edges[bucket + 1]
        # Leave the bucket's last slot closed, so a window at the end of one
        # bucket can't butt up against a window at the start of the next and
        # silently merge into a single long block. The final bucket has nothing
        # after it, so it may run to the end of the day.
        last_start = hi - WEEKDAY_WINDOW_SLOTS - (0 if bucket == n_buckets - 1 else 1)
        start = rng.randrange(lo, last_start + 1)
        keep.update(range(start, start + WEEKDAY_WINDOW_SLOTS))

    return [slots[i] for i in sorted(keep)]


def _generate_slot_boundaries(target_date: date, tz: ZoneInfo) -> list[tuple[datetime, datetime]]:
    """Generate the offered 30-minute slot boundaries for a given date.

    Returns a list of (start, end) tuples in the configured timezone.
    Mon-Fri: staggered windows inside 8am-4pm PT | Sat-Sun: 1pm-4pm PT, all open.
    Slots starting within MIN_LEAD_MINUTES are dropped.
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

    if not is_weekend:
        slots = _weekday_stagger(target_date, slots)

    cutoff = datetime.now(tz) + timedelta(minutes=MIN_LEAD_MINUTES)
    return [s for s in slots if s[0] >= cutoff]


def _extract_meet_link(event: dict) -> str:
    """Pull the video entry point (the Meet URL) out of an event's conferenceData."""
    for ep in event.get("conferenceData", {}).get("entryPoints", []) or []:
        if ep.get("entryPointType") == "video" and ep.get("uri"):
            return ep["uri"]
    return ""


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
        # 60-min: need two ADJACENT slots. Index adjacency is not enough — the
        # weekday grid is staggered, so slots[i+1] may be hours after slots[i].
        for i, (start, end) in enumerate(all_slots):
            if i + 1 < len(all_slots) and all_slots[i + 1][0] == end:
                available.append({
                    "start": start.isoformat(),
                    "end": (start + timedelta(minutes=60)).isoformat(),
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

    Offered hours (BOOKING_TIMEZONE): Mon-Fri staggered windows inside 8am-4pm,
    Sat-Sun 1pm-4pm. Excludes busy slots. Adds 15-min buffer between sessions.
    For 60-min sessions: only return slots where the adjacent slot is also free.

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
        # Fail closed: when the calendar's busy state is unknown we must NOT
        # assume every slot is free — that would let a booking land on a real
        # (calendar-busy) time. Surface the error so callers reject/skip rather
        # than over-offer. Both callers (GET /api/booking/slots and the free
        # booking's slot revalidation) already translate this into a 5xx/409.
        raise RuntimeError("calendar_freebusy_unavailable") from exc

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
        # 60-min: need two ADJACENT free slots. The staggered weekday grid has
        # gaps, so index i+1 being free does not mean it starts at i's end.
        for i in free_slot_indices:
            start, end = all_slots[i]
            if (i + 1) in free_set and all_slots[i + 1][0] == end:
                available.append({
                    "start": start.isoformat(),
                    "end": (start + timedelta(minutes=60)).isoformat(),
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

        # Google may still be provisioning the Meet room when insert() returns
        # (createRequest.status = 'pending'). The link is what both confirmation
        # emails are built around, so re-read the event a few times rather than
        # mailing "a link will follow" — nothing ever follows.
        meet_link = _extract_meet_link(created_event)
        for attempt in range(MEET_POLL_ATTEMPTS):
            if meet_link:
                break
            status = (
                created_event.get("conferenceData", {})
                .get("createRequest", {})
                .get("status", {})
                .get("statusCode")
            )
            if status == "failure":
                logger.error("[CALENDAR] Meet creation failed for event %s", event_id)
                break
            await asyncio.sleep(MEET_POLL_DELAY_S * (attempt + 1))
            try:
                created_event = await loop.run_in_executor(
                    None,
                    lambda: service.events().get(
                        calendarId=GOOGLE_CALENDAR_ID,
                        eventId=event_id,
                        conferenceDataVersion=1,
                    ).execute(),
                )
            except Exception as poll_exc:
                # The event exists; only the link lookup failed. Keep the booking.
                logger.warning("[CALENDAR] Meet link poll failed: %s", poll_exc)
                break
            meet_link = _extract_meet_link(created_event)

        if not meet_link:
            logger.error(
                "[CALENDAR] Event %s created without a Meet link — attendees get "
                "a calendar invite but no video link", event_id,
            )

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
