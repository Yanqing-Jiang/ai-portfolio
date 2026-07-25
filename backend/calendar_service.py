"""
Google Calendar API integration for booking system.

Function: get_available_slots — queries Google Calendar freebusy API for available slots.
Function: create_booking_event — creates a calendar event with Google Meet link.
Called from: backend.main (booking endpoints)
Invokes: Google Calendar API as the calendar owner (OAuth user token; see
google_oauth), falling back to a service account when one is configured.
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

from google_oauth import load_user_credentials, resolve_credentials_path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BOOKING_TIMEZONE = os.getenv("BOOKING_TIMEZONE", "America/Los_Angeles")
# Unset means the authenticated user's own calendar, which is what we want when
# authenticating as the owner. Only the service-account path needs an explicit ID.
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# Preferred auth: the owner's own OAuth token — the same file Gmail uses, so one
# `authorize_google.py` run configures both. See google_oauth for why a service
# account cannot invite external attendees on a consumer Gmail calendar.
GOOGLE_OAUTH_CREDENTIALS_PATH = os.getenv(
    "GOOGLE_OAUTH_CREDENTIALS_PATH",
    os.getenv("GMAIL_CREDENTIALS_PATH", "~/.gmail-mcp/credentials.json"),
)
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",  # freebusy
    "https://www.googleapis.com/auth/calendar.events",    # insert/get/delete
]

# Business hours (in BOOKING_TIMEZONE)
# Weekday (Mon-Fri): 9am-4pm PT, but only a few staggered windows are offered
# (see _weekday_stagger) | Weekend (Sat-Sun): 1pm-4pm PT, fully open.
WEEKDAY_HOUR_START = 9    # 9 AM
WEEKDAY_HOUR_END = 16     # 4 PM
WEEKEND_HOUR_START = 13   # 1 PM
WEEKEND_HOUR_END_H = 16   # 4 PM (hour component)
WEEKEND_HOUR_END_M = 0    # 4 PM (minute component)
BUFFER_MINUTES = 15       # buffer between sessions
SLOT_DURATION_MINUTES = 30  # base slot size

# Weekday stagger: how much of the 9am-4pm grid to actually publish.
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

# A standing meeting room (personal Google Meet / Zoom / Jitsi URL) used when no
# calendar is connected to mint a per-booking Meet link. Set it and every booking
# carries a real joinable link at confirmation time; leave it empty and the owner
# must send one by hand, prompted by an "ACTION NEEDED" alert.
BOOKING_FALLBACK_MEET_URL = os.getenv("BOOKING_FALLBACK_MEET_URL", "").strip()

# Don't publish a slot that starts within this many minutes — weekday hours now
# open at 9am, so without a lead time the afternoon visitor is shown morning
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
_calendar_auth_mode = "none"  # "oauth_user" | "service_account" | "none"
# Set only when we have established there is genuinely no credential to use (no
# token file, or one missing the required scopes). /api/booking/slots asks on
# every request, and re-deciding costs a file read plus a token refresh. The cost
# of caching is that authorizing needs a backend restart, which the setup doc
# says to do anyway. Transient failures are never cached here.
_calendar_unconfigured = False


def _calendar_id() -> str:
    """Which calendar to read and write.

    `primary` is the authenticated principal's own calendar — correct for the
    OAuth-user path and the reason that path needs no configuration at all. A
    service account's own primary calendar is useless, so that path is only
    reachable with an explicit GOOGLE_CALENDAR_ID (enforced below).
    """
    return GOOGLE_CALENDAR_ID or "primary"


def _oauth_user_credentials():
    """The owner's OAuth token, if it exists and carries the calendar scopes."""
    creds_path = resolve_credentials_path(GOOGLE_OAUTH_CREDENTIALS_PATH)
    if creds_path is None or not creds_path.exists():
        return None
    return load_user_credentials(creds_path, CALENDAR_SCOPES, log_prefix="[CALENDAR]")


def _service_account_credentials():
    """Fallback for a Workspace setup: a service account, optionally delegated."""
    if not GOOGLE_SERVICE_ACCOUNT_JSON or not GOOGLE_CALENDAR_ID:
        return None

    if not GOOGLE_CALENDAR_IMPERSONATE_USER:
        # Fail closed rather than report ready: an undelegated service account
        # books as itself, and Google will not email the invitation to the
        # attendee — the visitor would be "booked" with no invite and no Meet.
        logger.error(
            "[CALENDAR] Service account is configured without "
            "GOOGLE_CALENDAR_IMPERSONATE_USER, so it cannot invite attendees. "
            "Refusing to use it. Set the impersonated user (needs Workspace "
            "domain-wide delegation) or use the OAuth-user path "
            "(authorize_google.py)."
        )
        return None

    from google.oauth2 import service_account

    creds_info = json.loads(base64.b64decode(GOOGLE_SERVICE_ACCOUNT_JSON))
    credentials = service_account.Credentials.from_service_account_info(
        creds_info, scopes=CALENDAR_SCOPES,
    ).with_subject(GOOGLE_CALENDAR_IMPERSONATE_USER)
    logger.info(
        "[CALENDAR] Impersonating %s (domain-wide delegation)",
        GOOGLE_CALENDAR_IMPERSONATE_USER,
    )
    return credentials


def _get_calendar_service():
    """Lazy-initialize the Google Calendar API client.

    Prefers the owner's OAuth user token over a service account: only a real
    user can have Google deliver the invitation and Meet link to an external
    attendee without Workspace domain-wide delegation.
    """
    global _calendar_service, _calendar_configured, _calendar_auth_mode
    global _calendar_unconfigured

    if _calendar_service is not None:
        return _calendar_service
    # Only a settled "there is no credential here" verdict is cached. A timeout,
    # a half-written token file or a discovery error is transient, and caching it
    # would take booking offline until someone noticed and restarted.
    if _calendar_unconfigured:
        return None

    try:
        from googleapiclient.discovery import build

        credentials = _oauth_user_credentials()
        mode = "oauth_user"
        if credentials is None:
            credentials = _service_account_credentials()
            mode = "service_account"

        if credentials is None:
            logger.info(
                "[CALENDAR] No calendar connected — no OAuth token with calendar "
                "scope at %s, and no usable service account. Bookings still work "
                "from the published hours + the bookings table, but get no "
                "calendar event and no Meet link. To connect one, run "
                "`python3 backend/scripts/authorize_google.py`, then restart.",
                GOOGLE_OAUTH_CREDENTIALS_PATH,
            )
            _calendar_configured = False
            _calendar_auth_mode = "none"
            _calendar_unconfigured = True
            return None

        _calendar_service = build("calendar", "v3", credentials=credentials)
        _calendar_configured = True
        _calendar_auth_mode = mode
        logger.info(
            "[CALENDAR] Google Calendar API client initialized (auth=%s calendar=%s)",
            mode, _calendar_id(),
        )
        return _calendar_service

    except Exception as exc:
        # Deliberately NOT cached — see above.
        logger.error("[CALENDAR] Failed to initialize Google Calendar client: %s", exc)
        _calendar_configured = False
        _calendar_auth_mode = "none"
        return None


def is_calendar_configured() -> bool:
    """True when bookings can additionally be written to a real calendar.

    Not a precondition for booking — see get_available_slots. This reports
    whether a booking will also produce a calendar event and Meet link, which
    decides whether the owner has to send a link by hand.
    """
    return _get_calendar_service() is not None


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

    Mon-Fri spans a whole workday (9am-4pm = 14 slots); offering all of it reads
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
    Mon-Fri: staggered windows inside 9am-4pm PT | Sat-Sun: 1pm-4pm PT, all open.
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
# Session projection (shared by both availability modes)
# ---------------------------------------------------------------------------

def _project_sessions(
    all_slots: list[tuple[datetime, datetime]],
    free_slot_indices: list[int],
    duration: int,
) -> list[dict]:
    """Project free 30-minute boundaries onto bookable sessions.

    The ONE implementation of this rule. It is shared by both availability modes
    because `get_available_slots` is simultaneously the public offer (GET
    /api/booking/slots) and the revalidation source at booking time — if the two
    ever disagreed, the site would offer times its own writes then reject.
    """
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_available_slots(target_date: date, session_type: str = "30") -> list[dict]:
    """Return the available slot boundaries for a date.

    Offered hours (BOOKING_TIMEZONE): Mon-Fri staggered windows inside 9am-4pm,
    Sat-Sun 1pm-4pm. For 60-min sessions only slots whose neighbour is also free
    are returned.

    Two modes, one projection. With a calendar connected, busy periods are
    excluded via freebusy plus a 15-min buffer between sessions. With none
    connected the rule set alone defines availability — a supported production
    mode, not a stub: the published hours are narrowed by the bookings table in
    main.py, which refuses any slot already held or confirmed, and that is enough
    to stop double-booking through the site.

    The limit of the calendar-free mode, stated plainly: we cannot see
    commitments made anywhere else, so a slot the owner is personally busy for is
    still offered. Blocking that time means inserting a 'blocked' row (see
    BOOKING_NOTIFICATIONS.md); connecting a calendar upgrades this path to a real
    freebusy check with no other change.

    Returns: [{"start": "ISO8601 with offset", "end": "ISO8601 with offset"}]
    """
    tz = ZoneInfo(BOOKING_TIMEZONE)
    duration = SESSION_DURATIONS.get(session_type, 30)

    all_slots = _generate_slot_boundaries(target_date, tz)
    if not all_slots:
        return []

    service = _get_calendar_service()
    if service is None:
        # Nothing to exclude: every published slot is on offer. This used to be a
        # second function with its own copy of the 30/60-minute projection below —
        # two implementations of the rule that has to stay byte-identical between
        # the public offer and the booking-time revalidation.
        logger.info("[CALENDAR] No calendar connected — offering the published hours")
        return _project_sessions(all_slots, list(range(len(all_slots))), duration)

    # Query freebusy for the entire business day
    cal_id = _calendar_id()
    time_min = all_slots[0][0].isoformat()
    time_max = (all_slots[-1][1] + timedelta(minutes=BUFFER_MINUTES)).isoformat()

    try:
        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "timeZone": BOOKING_TIMEZONE,
            "items": [{"id": cal_id}],
        }

        # Google API client is synchronous — call in thread
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: service.freebusy().query(body=body).execute(),
        )

        calendars = result.get("calendars", {})
        # Keyed by the id we asked for; fall back to the sole entry so an alias
        # ("primary" resolving to the address) cannot silently read as all-free.
        entry = calendars.get(cal_id)
        if entry is None and len(calendars) == 1:
            entry = next(iter(calendars.values()))
        if entry is None:
            raise RuntimeError(f"freebusy returned no data for calendar {cal_id!r}")

        # Google answers HTTP 200 with a per-calendar `errors` array for
        # notFound/internalError. Reading `busy` off that would report an empty
        # busy list — i.e. the whole day free — and let a booking land on top of
        # a real event. Treat it as unknown, not as free.
        if entry.get("errors"):
            raise RuntimeError(
                f"freebusy errors for calendar {cal_id!r}: {entry['errors']}"
            )
        # Same reasoning for a malformed response: absent `busy` is unknown, not
        # empty. An explicit empty list is legitimate and means genuinely free.
        busy_periods = entry.get("busy")
        if not isinstance(busy_periods, list):
            raise RuntimeError(
                f"freebusy returned no busy list for calendar {cal_id!r}"
            )

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

    return _project_sessions(all_slots, free_slot_indices, duration)


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

    Returns: {"event_id": str, "meet_link": str} — both empty when no calendar is
    connected, which is a supported mode: the booking is real (it lives in the
    bookings table) and the owner is alerted to send a video link by hand.
    Raises: RuntimeError only when a calendar IS connected and the write fails —
    that is a genuine failure and must not be reported as a confirmed booking.
    """
    tz = ZoneInfo(BOOKING_TIMEZONE)
    duration = SESSION_DURATIONS.get(session_type, 30)
    slot_end = slot_start + timedelta(minutes=duration)

    service = _get_calendar_service()
    if service is None:
        # No calendar to write to. Don't fail the booking over it — the DB row is
        # what makes the slot held. If a standing room is configured the client
        # still gets a joinable link; otherwise send_admin_booking_alert raises an
        # "ACTION NEEDED — no Meet link" flag so the call still gets one.
        logger.info(
            "[CALENDAR] No calendar connected — booking %s recorded without an "
            "event (standing room link: %s)", email, bool(BOOKING_FALLBACK_MEET_URL),
        )
        return {"event_id": "", "meet_link": BOOKING_FALLBACK_MEET_URL}

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
                calendarId=_calendar_id(),
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
                        calendarId=_calendar_id(),
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
    Returns True on success, False when there is no calendar to delete from.
    Raises RuntimeError if deletion fails against a connected calendar.
    """
    service = _get_calendar_service()
    if service is None:
        # Nothing to delete. Callers only reach this with a non-empty event id, so
        # this means the calendar was disconnected after the event was written —
        # worth a warning, but it must not block the cancellation itself.
        logger.warning(
            "[CALENDAR] Cannot delete event %s — no calendar connected", calendar_event_id,
        )
        return False

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: service.events().delete(
                calendarId=_calendar_id(),
                eventId=calendar_event_id,
                sendUpdates="all",
            ).execute(),
        )
        logger.info("[CALENDAR] Event deleted: %s", calendar_event_id)
        return True
    except Exception as exc:
        logger.error("[CALENDAR] Event deletion failed: %s", exc)
        raise RuntimeError(f"Calendar event deletion failed: {exc}") from exc
