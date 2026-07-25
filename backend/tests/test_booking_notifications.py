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


# --- Telegram signature ------------------------------------------------------

def test_booking_notification_accepts_the_status_kwarg():
    """cancel/reschedule pass status=; before the fix this raised TypeError into
    a bare except, so those notifications never sent."""
    import inspect

    import telegram_service as ts

    assert "status" in inspect.signature(ts.send_booking_notification).parameters
