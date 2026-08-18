"""Booking notification guarantees — the free-call path must never claim a
booking is done while silently telling nobody.

Both email senders return False instead of raising, so these tests pin the
contract that /api/booking/free reports what actually happened, and that the
Meet link is chased down before the emails are built around it.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import calendar_service as cs  # noqa: E402
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_buckets():
    main._RATE_BUCKETS.clear()
    yield
    main._RATE_BUCKETS.clear()


@pytest.fixture
def slot() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0).isoformat()


def _book(monkeypatch, slot, *, owner_sent=True, requestor_sent=True, meet="https://meet.google.com/abc"):
    """POST a free booking with the calendar + both senders stubbed."""
    calls: dict[str, list] = {"admin": [], "client": [], "telegram": []}

    async def fake_event(**kwargs):
        return {"event_id": "evt_1", "meet_link": meet}

    async def fake_admin(**kwargs):
        calls["admin"].append(kwargs)
        return owner_sent

    async def fake_client(**kwargs):
        calls["client"].append(kwargs)
        return requestor_sent

    async def fake_telegram(**kwargs):
        calls["telegram"].append(kwargs)
        return True

    async def no_slot_check(_slot_start):
        return None

    async def no_pool():
        return None

    async def no_brief_link(*a, **k):
        return None

    monkeypatch.setattr(main, "create_booking_event", fake_event)
    monkeypatch.setattr(main, "send_admin_booking_alert", fake_admin)
    monkeypatch.setattr(main, "send_booking_confirmation_email", fake_client)
    monkeypatch.setattr(main, "send_booking_notification", fake_telegram)
    monkeypatch.setattr(main, "_assert_slot_offered", no_slot_check)
    monkeypatch.setattr(main, "_get_booking_pool", no_pool)
    monkeypatch.setattr(main, "_link_brief_to_booking", no_brief_link)

    with TestClient(main.app) as client:
        res = client.post("/api/booking/free", json={
            "slot_start": slot, "name": "Test Person", "email": "test@example.com",
            "notes": "smoke",
        })
    return res, calls


def test_both_parties_are_emailed_with_the_meet_link(monkeypatch, slot):
    res, calls = _book(monkeypatch, slot)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "confirmed"
    assert body["notification_status"] == {"owner_email": "sent", "requestor_email": "sent"}
    # The owner alert and the requestor confirmation both carry the Meet link.
    assert calls["admin"][0]["meet_link"] == "https://meet.google.com/abc"
    assert calls["client"][0]["meet_link"] == "https://meet.google.com/abc"
    assert calls["client"][0]["email"] == "test@example.com"


@pytest.mark.parametrize(
    "owner_sent,requestor_sent,expected",
    [
        (False, True, {"owner_email": "failed", "requestor_email": "sent"}),
        (True, False, {"owner_email": "sent", "requestor_email": "failed"}),
        (False, False, {"owner_email": "failed", "requestor_email": "failed"}),
    ],
)
def test_a_failed_send_is_reported_not_swallowed(monkeypatch, slot, owner_sent, requestor_sent, expected):
    res, _ = _book(monkeypatch, slot, owner_sent=owner_sent, requestor_sent=requestor_sent)
    assert res.status_code == 200  # the event exists; the booking still stands
    assert res.json()["notification_status"] == expected


def test_calendar_failure_still_alerts_the_owner(monkeypatch, slot):
    """A prospect turned away at the last click must not be invisible."""
    alerts: list[dict] = []

    async def boom(**kwargs):
        raise RuntimeError("Google Calendar not configured")

    async def fake_admin(**kwargs):
        alerts.append(kwargs)
        return True

    async def no_slot_check(_slot_start):
        return None

    async def no_pool():
        return None

    monkeypatch.setattr(main, "create_booking_event", boom)
    monkeypatch.setattr(main, "send_admin_booking_alert", fake_admin)
    monkeypatch.setattr(main, "_assert_slot_offered", no_slot_check)
    monkeypatch.setattr(main, "_get_booking_pool", no_pool)

    with TestClient(main.app) as client:
        res = client.post("/api/booking/free", json={
            "slot_start": slot, "name": "Test Person", "email": "test@example.com",
        })

    assert res.status_code == 502
    assert "not been booked" in res.json()["detail"]
    assert len(alerts) == 1
    assert alerts[0]["failure_reason"]
    assert "not configured" in alerts[0]["failure_reason"]


# --- Meet link resolution ----------------------------------------------------

@pytest.mark.parametrize("uri", [
    "http://meet.google.com/abc-defg-hij",
    "https://evil.example/abc-defg-hij",
    "https://meet.google.com.evil.example/abc-defg-hij",
    "https://meet.google.com/",
])
def test_invalid_meet_video_urls_are_rejected(uri):
    event = {
        "conferenceData": {
            "entryPoints": [{"entryPointType": "video", "uri": uri}],
        },
    }

    assert cs._extract_meet_link(event) == ""


def test_canonical_google_meet_video_url_is_accepted():
    event = {
        "conferenceData": {
            "entryPoints": [{
                "entryPointType": "video",
                "uri": "https://meet.google.com/abc-defg-hij",
            }],
        },
    }

    assert cs._extract_meet_link(event) == "https://meet.google.com/abc-defg-hij"

class _FakeEvents:
    """Mimics the Google client: insert() returns a pending conference, and the
    Meet link only shows up on a later events.get()."""

    def __init__(self, link_after: int, fail: bool = False):
        self.link_after = link_after
        self.fail = fail
        self.gets = 0

    def _payload(self, with_link: bool):
        conference = {"createRequest": {"status": {"statusCode": "failure" if self.fail else "pending"}}}
        if with_link:
            conference = {"entryPoints": [{"entryPointType": "video", "uri": "https://meet.google.com/late"}]}
        return {"id": "evt_1", "conferenceData": conference}

    def insert(self, **kwargs):
        return _Exec(self._payload(self.link_after == 0))

    def get(self, **kwargs):
        self.gets += 1
        return _Exec(self._payload(self.gets >= self.link_after))


class _Exec:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _FakeService:
    def __init__(self, events):
        self._events = events

    def events(self):
        return self._events


@pytest.mark.asyncio
async def test_meet_link_is_picked_up_on_a_later_poll(monkeypatch):
    events = _FakeEvents(link_after=2)
    monkeypatch.setattr(cs, "_get_calendar_service", lambda: _FakeService(events))
    monkeypatch.setattr(cs, "MEET_POLL_DELAY_S", 0)

    result = await cs.create_booking_event(
        session_type="30", slot_start=datetime.now(timezone.utc) + timedelta(days=3),
        name="Test", email="test@example.com",
    )
    assert result["meet_link"] == "https://meet.google.com/late"
    assert events.gets == 2  # polled until it appeared


@pytest.mark.asyncio
async def test_booking_survives_a_meet_link_that_never_appears(monkeypatch):
    """No link is bad, but losing the booking over it is worse."""
    events = _FakeEvents(link_after=99)
    monkeypatch.setattr(cs, "_get_calendar_service", lambda: _FakeService(events))
    monkeypatch.setattr(cs, "MEET_POLL_DELAY_S", 0)

    result = await cs.create_booking_event(
        session_type="30", slot_start=datetime.now(timezone.utc) + timedelta(days=3),
        name="Test", email="test@example.com",
    )
    assert result["event_id"] == "evt_1"
    assert result["meet_link"] == ""
    assert events.gets == cs.MEET_POLL_ATTEMPTS


@pytest.mark.asyncio
async def test_meet_creation_failure_stops_polling(monkeypatch):
    events = _FakeEvents(link_after=99, fail=True)
    monkeypatch.setattr(cs, "_get_calendar_service", lambda: _FakeService(events))
    monkeypatch.setattr(cs, "MEET_POLL_DELAY_S", 0)

    result = await cs.create_booking_event(
        session_type="30", slot_start=datetime.now(timezone.utc) + timedelta(days=3),
        name="Test", email="test@example.com",
    )
    assert result["meet_link"] == ""
    assert events.gets == 0  # a declared failure is not retried


# --- Production must not confirm what it cannot record -----------------------

def test_production_refuses_to_book_without_the_bookings_table(monkeypatch, slot):
    """No hold means nothing stops two visitors taking the same slot, and a
    confirmed call leaves no row to reschedule or cancel from."""
    async def no_pool():
        return None

    async def no_slot_check(_slot_start):
        return None

    async def must_not_run(**_kwargs):
        raise AssertionError("the calendar must not be touched without a hold")

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(main, "_get_booking_pool", no_pool)
    monkeypatch.setattr(main, "_assert_slot_offered", no_slot_check)
    monkeypatch.setattr(main, "create_booking_event", must_not_run)

    with TestClient(main.app) as client:
        res = client.post("/api/booking/free", json={
            "slot_start": slot, "name": "Test Person", "email": "test@example.com",
        })

    assert res.status_code == 503
    assert "email" in res.json()["detail"].lower()


def test_development_still_books_without_a_database(monkeypatch, slot):
    """Local work must not require Supabase."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    res, _ = _book(monkeypatch, slot)
    assert res.status_code == 200


# --- No Google Calendar is a supported mode -----------------------------------

def _book_against_real_calendar_layer(monkeypatch, slot):
    """POST a free booking using the REAL create_booking_event.

    The other tests stub it out, so they cannot tell whether an absent calendar
    fails the booking. This drives calendar_service itself.
    """
    calls: dict[str, list] = {"admin": [], "client": []}

    async def fake_admin(**kwargs):
        calls["admin"].append(kwargs)
        return True

    async def fake_client(**kwargs):
        calls["client"].append(kwargs)
        return True

    async def fake_telegram(**kwargs):
        return True

    async def no_slot_check(_slot_start):
        return None

    async def no_pool():
        return None

    async def no_brief_link(*a, **k):
        return None

    monkeypatch.setattr(main, "send_admin_booking_alert", fake_admin)
    monkeypatch.setattr(main, "send_booking_confirmation_email", fake_client)
    monkeypatch.setattr(main, "send_booking_notification", fake_telegram)
    monkeypatch.setattr(main, "_assert_slot_offered", no_slot_check)
    monkeypatch.setattr(main, "_get_booking_pool", no_pool)
    monkeypatch.setattr(main, "_link_brief_to_booking", no_brief_link)

    with TestClient(main.app) as client:
        res = client.post("/api/booking/free", json={
            "slot_start": slot, "name": "Test Person", "email": "test@example.com",
        })
    return res, calls


def test_a_booking_is_confirmed_with_no_calendar_connected(monkeypatch, slot):
    """Booking must not depend on Google Calendar.

    Availability is the published hours narrowed by the bookings table. With no
    calendar the call is still real — it just has no calendar event and no Meet
    link, so the owner is told to send one by hand.
    """
    monkeypatch.setattr(cs, "_get_calendar_service", lambda: None)
    monkeypatch.setenv("ENVIRONMENT", "development")

    res, calls = _book_against_real_calendar_layer(monkeypatch, slot)

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "confirmed"
    assert not body.get("meet_link")
    # The owner has to know a link is owed, or the client joins nothing.
    assert calls["admin"][0]["meet_link"] in (None, "")
    assert calls["client"], "the requestor is still told the call is booked"


def test_a_connected_calendar_that_fails_still_blocks_the_booking(monkeypatch, slot):
    """The fail-closed rule survives: 'no calendar' is fine, 'broken' is not."""
    class _Boom:
        def events(self):
            raise RuntimeError("calendar exploded")

    monkeypatch.setattr(cs, "_get_calendar_service", lambda: _Boom())
    monkeypatch.setenv("ENVIRONMENT", "development")

    res, _ = _book_against_real_calendar_layer(monkeypatch, slot)

    assert res.status_code >= 400, "a broken calendar must not read as confirmed"


@pytest.mark.asyncio
async def test_deleting_an_event_without_a_calendar_does_not_raise(monkeypatch):
    """Cancelling a calendar-free booking must not blow up on the delete step."""
    monkeypatch.setattr(cs, "_get_calendar_service", lambda: None)
    assert await cs.delete_booking_event("evt_that_never_existed") is False


# --- Telegram -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancellation_notification_actually_sends(monkeypatch):
    """cancel/reschedule pass status=; before the fix this raised TypeError into
    a bare except, so those notifications had never been delivered."""
    import telegram_service as ts

    sent: dict = {}

    class _FakeResponse:
        def raise_for_status(self):
            return None

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def post(self, url, json=None):
            sent["url"] = url
            sent["payload"] = json
            return _FakeResponse()

    monkeypatch.setattr(ts, "TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setattr(ts, "TELEGRAM_CHAT_ID", "chat")
    monkeypatch.setattr(ts.httpx, "AsyncClient", lambda **_kw: _FakeClient())

    ok = await ts.send_booking_notification(
        name="Test Person", email="test@example.com", session_type="fit",
        slot_start="2099-01-01T13:00:00-08:00", status="CANCELLED",
    )

    assert ok is True
    assert "CANCELLED" in sent["payload"]["text"]


# --- never report a booking we did not persist ---------------------------------

def test_a_failed_hold_promotion_is_not_reported_as_confirmed(monkeypatch, slot):
    """The hold -> confirmed UPDATE is what makes the booking exist. Swallowing
    its failure meant the row stayed 'hold', got swept 30 minutes later, and freed
    the slot — while the visitor held a "confirmed" response and an email."""
    removed: list = []

    class _Conn:
        async def execute(self, sql, *args):
            s = " ".join(sql.split())
            if s.startswith("INSERT INTO bookings"):
                return "INSERT 0 1"
            if "SET status = 'confirmed'" in s:
                return "UPDATE 0"        # lost the row: swept, or already taken
            return "UPDATE 0"

    class _Pool:
        def acquire(self):
            class _Ctx:
                async def __aenter__(_s):
                    return _Conn()

                async def __aexit__(_s, *_e):
                    return False
            return _Ctx()

    async def get_pool():
        return _Pool()

    async def no_slot_check(_slot_start, _session_type="30"):
        return None

    async def fake_event(**_kw):
        return {"event_id": "evt_ghost", "meet_link": ""}

    async def remove(event_id):
        removed.append(event_id)
        return True

    async def noop(**_kw):
        return True

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(main, "_get_booking_pool", get_pool)
    monkeypatch.setattr(main, "_assert_slot_offered", no_slot_check)
    monkeypatch.setattr(main, "create_booking_event", fake_event)
    monkeypatch.setattr(main, "delete_booking_event", remove)
    monkeypatch.setattr(main, "send_admin_booking_alert", noop)
    monkeypatch.setattr(main, "send_booking_confirmation_email", noop)
    monkeypatch.setattr(main, "send_booking_notification", noop)

    with TestClient(main.app) as client:
        res = client.post("/api/booking/free", json={
            "slot_start": slot, "name": "Test Person", "email": "test@example.com",
        })

    assert res.status_code == 503
    assert "not been booked" in res.json()["detail"]
    # The calendar event we created must not be left behind as a ghost.
    assert removed == ["evt_ghost"]


def test_paid_checkout_refuses_without_a_database_in_production(monkeypatch):
    """It used to fall through and take a PAYMENT for a slot nothing was holding."""
    async def no_pool():
        return None

    async def no_slot_check(_slot_start, _session_type="30"):
        return None

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(main, "_get_booking_pool", no_pool)
    monkeypatch.setattr(main, "_assert_slot_offered", no_slot_check)
    monkeypatch.setattr(main, "STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setattr(main, "BOOKING_PRICE_MAP", {"30": "price_x", "60": "price_y"})

    class _Boom:
        class checkout:
            class Session:
                @staticmethod
                def create(**_kw):
                    raise AssertionError("Stripe must not be called without a hold")

    monkeypatch.setattr(main, "stripe", _Boom)

    future = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0)
    with TestClient(main.app) as client:
        res = client.post("/api/booking/checkout", json={
            "session_type": "30", "slot_start": future.isoformat(),
            "name": "T", "email": "t@example.com",
            "success_url": "https://x/s", "cancel_url": "https://x/c",
        })

    assert res.status_code == 503
    assert "unavailable" in res.json()["detail"].lower()
