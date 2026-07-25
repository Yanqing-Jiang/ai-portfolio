"""Reschedule and cancel — the authenticated lifecycle endpoints.

These live behind a Supabase JWT and were never exercised: the table has 0 rows,
so `RescheduleFlow` was live UI over a path that could not succeed. The fake
connection below deliberately enforces ONE real schema rule — the UNIQUE index on
`stripe_session_id` — because that constraint is what made every reschedule fail.
A fake that ignores it would let the bug pass.
"""
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402
from rate_limiter import ParsedToken  # noqa: E402

OWNER = ParsedToken(user_id=str(uuid.uuid4()), email="client@example.com")


class _UniqueViolation(Exception):
    """Stands in for asyncpg.exceptions.UniqueViolationError."""


class _FakeConn:
    """In-memory `bookings` with the stripe_session_id UNIQUE index enforced.

    Statements are matched by keyword rather than parsed — enough to model the
    reschedule transaction (one UPDATE of the old row, one INSERT of the new).
    """

    def __init__(self, rows: dict):
        self.rows = rows

    def _session_ids(self, exclude_id=None):
        return {r["stripe_session_id"] for rid, r in self.rows.items() if rid != exclude_id}

    async def fetchrow(self, sql, *args):
        if "RECURSIVE chain" in sql:
            # Walk rescheduled_from to the root, like the real CTE.
            rid, depth = args[0], 0
            while True:
                row = self.rows.get(rid)
                parent = row.get("rescheduled_from") if row else None
                if parent is None or parent not in self.rows:
                    break
                rid, depth = parent, depth + 1
            return {"root_id": str(rid), "depth": depth}
        # A COPY, like asyncpg's immutable Record. Handing back the live dict would
        # let a later in-place UPDATE retroactively change what the caller read.
        row = self.rows.get(args[0])
        return dict(row) if row is not None else None

    async def fetch(self, _sql, *args):
        return [dict(r) for r in self.rows.values()]

    async def execute(self, sql, *args):
        s = " ".join(sql.split())
        if s.startswith("UPDATE bookings SET status = 'rescheduled'"):
            row = self.rows[args[0]]
            row["status"] = "rescheduled"
            if "stripe_session_id = 'superseded_'" in s:
                row["stripe_session_id"] = f"superseded_{row['id']}"
            return "UPDATE 1"
        if s.startswith("INSERT INTO bookings"):
            new = {
                "id": args[0], "stripe_session_id": args[1], "stripe_event_id": args[2],
                "session_type": args[3], "slot_start": args[4], "slot_end": args[5],
                "client_name": args[6], "client_email": args[7], "notes": args[8],
                "status": "confirmed", "amount_cents": args[9], "user_id": args[10],
                "rescheduled_from": args[11], "calendar_event_id": None, "meet_link": None,
            }
            if new["stripe_session_id"] in self._session_ids(exclude_id=new["id"]):
                raise _UniqueViolation(
                    'duplicate key value violates unique constraint '
                    '"bookings_stripe_session_id_key"'
                )
            self.rows[new["id"]] = new
            return "INSERT 0 1"
        if s.startswith("UPDATE bookings SET calendar_event_id"):
            return "UPDATE 1"
        return "UPDATE 0"

    def transaction(self):
        rows = self.rows
        conn = self

        class _Tx:
            async def __aenter__(_self):
                _self.snapshot = {k: dict(v) for k, v in rows.items()}
                return _self

            async def __aexit__(_self, exc_type, *_rest):
                if exc_type is not None:          # roll back, like a real transaction
                    conn.rows.clear()
                    conn.rows.update(_self.snapshot)
                return False

        return _Tx()


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        conn = self._conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *_exc):
                return False

        return _Ctx()


@pytest.fixture
def confirmed_booking():
    """A confirmed booking 5 days out, paid, owned by OWNER."""
    bid = uuid.uuid4()
    start = datetime.now(timezone.utc) + timedelta(days=5)
    return bid, {
        "id": bid,
        "stripe_session_id": "cs_test_the_real_one",
        "stripe_event_id": "evt_1",
        "session_type": "30",
        "slot_start": start.replace(microsecond=0),
        "slot_end": (start + timedelta(minutes=30)).replace(microsecond=0),
        "client_name": "Test Person",
        "client_email": OWNER.email,
        "notes": None,
        "status": "confirmed",
        "amount_cents": 5000,
        "user_id": uuid.UUID(OWNER.user_id),
        "calendar_event_id": None,
        "meet_link": None,
        "rescheduled_from": None,
    }


def _reschedule(monkeypatch, rows, new_slot_iso, emails=None):
    conn = _FakeConn(rows)

    async def get_pool():
        return _FakePool(conn)

    async def offered(_slot, _session_type="30"):
        return None      # the new time is a published slot

    async def no_cal(**_kw):
        return {"event_id": "", "meet_link": ""}

    async def noop(*_a, **_k):
        return True

    async def capture_email(**kwargs):
        if emails is not None:
            emails.append(kwargs)
        return True

    monkeypatch.setattr(main, "_get_booking_pool", get_pool)
    monkeypatch.setattr(main, "_assert_slot_offered", offered)
    monkeypatch.setattr(main, "create_booking_event", no_cal)
    monkeypatch.setattr(main, "delete_booking_event", noop)
    monkeypatch.setattr(main, "send_booking_notification", noop)
    monkeypatch.setattr(main, "send_booking_confirmation_email", capture_email)

    main.app.dependency_overrides[main.require_auth] = lambda: OWNER
    try:
        with TestClient(main.app) as client:
            booking_id = next(iter(rows))
            return client.post(
                f"/api/booking/{booking_id}/reschedule",
                json={"new_slot_start": new_slot_iso},
            ), conn
    finally:
        main.app.dependency_overrides.clear()


def test_reschedule_succeeds_and_keeps_the_real_stripe_session_id(monkeypatch, confirmed_booking):
    """Before the fix this was impossible: the new row reused the old row's
    stripe_session_id against a UNIQUE index, so the INSERT always raised and the
    generic handler reported 409 'that time is no longer available' — for every
    reschedule of every booking."""
    bid, booking = confirmed_booking
    rows = {bid: booking}
    new_slot = (datetime.now(timezone.utc) + timedelta(days=6)).replace(microsecond=0)

    res, conn = _reschedule(monkeypatch, rows, new_slot.isoformat())

    assert res.status_code == 200, res.text
    assert res.json()["success"] is True

    old = conn.rows[bid]
    new = next(r for rid, r in conn.rows.items() if rid != bid)

    assert old["status"] == "rescheduled"
    assert old["stripe_session_id"] == f"superseded_{bid}"
    # The refund path reads the session id off the CURRENT row, so the live
    # booking must carry the genuine one.
    assert new["stripe_session_id"] == "cs_test_the_real_one"
    assert new["status"] == "confirmed"
    assert new["rescheduled_from"] == bid


def test_rescheduling_twice_does_not_collide(monkeypatch, confirmed_booking):
    """'superseded_' + the previous VALUE would collide on the second hop;
    keying on the row's own primary key cannot."""
    bid, booking = confirmed_booking
    rows = {bid: booking}

    first = (datetime.now(timezone.utc) + timedelta(days=6)).replace(microsecond=0)
    res1, conn = _reschedule(monkeypatch, rows, first.isoformat())
    assert res1.status_code == 200, res1.text

    second_id = next(rid for rid in conn.rows if rid != bid)
    second = (datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0)

    ordered = {second_id: conn.rows[second_id], bid: conn.rows[bid]}
    res2, conn2 = _reschedule(monkeypatch, ordered, second.isoformat())

    assert res2.status_code == 200, res2.text
    live = [r for r in conn2.rows.values() if r["status"] == "confirmed"]
    assert len(live) == 1
    assert live[0]["stripe_session_id"] == "cs_test_the_real_one"


def test_reschedule_emails_the_client_with_a_moving_calendar_update(monkeypatch, confirmed_booking):
    """Rescheduling used to notify only the owner over Telegram, leaving the client
    with the old time in their inbox and calendar. The update must reuse the
    ORIGINAL UID with a higher SEQUENCE, or their calendar gains a second event
    instead of moving the first."""
    bid, booking = confirmed_booking
    rows = {bid: booking}
    emails: list[dict] = []
    new_slot = (datetime.now(timezone.utc) + timedelta(days=6)).replace(microsecond=0)

    res, conn = _reschedule(monkeypatch, rows, new_slot.isoformat(), emails=emails)
    assert res.status_code == 200, res.text

    assert len(emails) == 1, "the client must be told the call moved"
    sent = emails[0]
    assert sent["kind"] == "rescheduled"
    assert sent["email"] == booking["client_email"]
    assert sent["booking_id"] == str(bid), "UID stays the chain root"
    assert sent["ics_sequence"] == 1, "a revision, so calendars accept the move"
    assert sent["slot_start"] == new_slot.isoformat()


def test_a_second_reschedule_keeps_the_same_uid_and_bumps_sequence_again(monkeypatch, confirmed_booking):
    bid, booking = confirmed_booking
    rows = {bid: booking}
    emails: list[dict] = []

    first = (datetime.now(timezone.utc) + timedelta(days=6)).replace(microsecond=0)
    res1, conn = _reschedule(monkeypatch, rows, first.isoformat(), emails=emails)
    assert res1.status_code == 200

    second_id = next(rid for rid in conn.rows if rid != bid)
    ordered = {second_id: conn.rows[second_id], bid: conn.rows[bid]}
    second = (datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0)
    res2, _ = _reschedule(monkeypatch, ordered, second.isoformat(), emails=emails)
    assert res2.status_code == 200

    assert [e["ics_sequence"] for e in emails] == [1, 2]
    assert {e["booking_id"] for e in emails} == {str(bid)}, "one calendar entry, revised twice"


def test_reschedule_refuses_a_time_we_do_not_offer(monkeypatch, confirmed_booking):
    """Reschedule was a way around published hours — any future instant passed."""
    bid, booking = confirmed_booking
    rows = {bid: booking}
    conn = _FakeConn(rows)

    async def get_pool():
        return _FakePool(conn)

    from fastapi import HTTPException

    async def not_offered(_slot, _session_type="30"):
        raise HTTPException(status_code=409, detail="That time is no longer available.")

    monkeypatch.setattr(main, "_get_booking_pool", get_pool)
    monkeypatch.setattr(main, "_assert_slot_offered", not_offered)

    main.app.dependency_overrides[main.require_auth] = lambda: OWNER
    try:
        three_am = (datetime.now(timezone.utc) + timedelta(days=6)).replace(
            hour=10, minute=0, second=0, microsecond=0)  # 03:00 PT
        with TestClient(main.app) as client:
            res = client.post(f"/api/booking/{bid}/reschedule",
                              json={"new_slot_start": three_am.isoformat()})
    finally:
        main.app.dependency_overrides.clear()

    assert res.status_code == 409
    # Nothing moved.
    assert conn.rows[bid]["status"] == "confirmed"
    assert len(conn.rows) == 1


# --- the calendar file itself -------------------------------------------------

def _ics(**over):
    import email_service as es
    args = dict(
        booking_id="11111111-2222-3333-4444-555555555555",
        slot_start_iso="2026-08-05T13:00:00-07:00",
        session_type="30",
        client_name="Test Person",
        client_email="c@example.com",
        meet_link="https://meet.google.com/abc-defg-hij",
    )
    args.update(over)
    return es.build_booking_ics(**args)


def test_ics_times_are_utc_and_match_the_slot():
    """13:00 Pacific is 20:00Z. A local-time DTSTART without a VTIMEZONE block is
    the classic way to put a call in someone's calendar an hour off."""
    ics = _ics()
    assert "DTSTART:20260805T200000Z" in ics
    assert "DTEND:20260805T203000Z" in ics


def test_ics_is_crlf_terminated_and_folded_on_utf8_boundaries():
    """RFC 5545 requires CRLF and <=75 octets per line. Folding on characters
    instead of octets corrupts non-ASCII names."""
    ics = _ics(client_name="Aymeric Déchamps de la Trés Longue Maison Européenne")
    assert ics.endswith("\r\n")
    for line in ics.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75 or line.startswith(" "), line
    assert "Déchamps" in ics


def test_ics_escapes_separators_that_would_break_parsing():
    ics = _ics(client_name="Acme, Inc; trading as Acme")
    assert r"Acme\, Inc\; trading" in ics


def test_a_cancellation_withdraws_the_same_event():
    """Same UID + METHOD:CANCEL is what removes the event the client already has."""
    live = _ics(sequence=0)
    gone = _ics(sequence=1, cancelled=True)
    uid = "UID:11111111-2222-3333-4444-555555555555@yanqing.app"
    assert uid in live and uid in gone
    assert "METHOD:REQUEST" in live and "METHOD:CANCEL" in gone
    assert "STATUS:CONFIRMED" in live and "STATUS:CANCELLED" in gone
    assert "SEQUENCE:1" in gone
    assert "VALARM" not in gone, "no reminder for a cancelled call"


def test_a_booking_email_carries_the_calendar_part(monkeypatch):
    """End to end through the MIME builder: the message must actually contain a
    text/calendar part with the right METHOD, or nothing lands in any calendar."""
    import base64
    import email as _email
    import email_service as es

    captured: dict = {}

    class _Msgs:
        def send(self, userId=None, body=None):
            captured["raw"] = body["raw"]
            class _Ex:
                def execute(_s):
                    return {"id": "m1"}
            return _Ex()

    class _Users:
        def messages(self):
            return _Msgs()

    class _Svc:
        def users(self):
            return _Users()

    monkeypatch.setattr(es, "_get_gmail_service", lambda: _Svc())
    monkeypatch.setattr(es, "GMAIL_FROM_EMAIL", "owner@example.com")

    import asyncio
    ok = asyncio.get_event_loop().run_until_complete(
        es.send_booking_confirmation_email(
            name="Test Person", email="c@example.com", session_type="30",
            slot_start="2026-08-05T13:00:00-07:00",
            meet_link="https://meet.google.com/x", kind="confirmed",
            booking_id="11111111-2222-3333-4444-555555555555", ics_sequence=0,
        )
    )
    assert ok is True

    msg = _email.message_from_bytes(base64.urlsafe_b64decode(captured["raw"]))
    cal = [p for p in msg.walk() if p.get_content_type() == "text/calendar"]
    assert len(cal) == 1, [p.get_content_type() for p in msg.walk()]
    assert cal[0].get_param("method") == "REQUEST"
    body = cal[0].get_payload(decode=True).decode("utf-8")
    assert "BEGIN:VCALENDAR" in body and "DTSTART:20260805T200000Z" in body
    # The human-readable parts survive alongside it.
    assert any(p.get_content_type() == "text/html" for p in msg.walk())
    assert any(p.get_content_type() == "text/plain" for p in msg.walk())


def test_no_calendar_part_without_a_stable_uid(monkeypatch):
    """A file we could never correct later is worse than no file."""
    import base64
    import email as _email
    import email_service as es

    captured: dict = {}

    class _Msgs:
        def send(self, userId=None, body=None):
            captured["raw"] = body["raw"]
            class _Ex:
                def execute(_s):
                    return {"id": "m1"}
            return _Ex()

    class _Users:
        def messages(self):
            return _Msgs()

    class _Svc:
        def users(self):
            return _Users()

    monkeypatch.setattr(es, "_get_gmail_service", lambda: _Svc())

    import asyncio
    asyncio.get_event_loop().run_until_complete(
        es.send_booking_confirmation_email(
            name="T", email="c@example.com", session_type="30",
            slot_start="2026-08-05T13:00:00-07:00", booking_id=None,
        )
    )
    msg = _email.message_from_bytes(base64.urlsafe_b64decode(captured["raw"]))
    assert not [p for p in msg.walk() if p.get_content_type() == "text/calendar"]
