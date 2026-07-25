"""The booking lifecycle after payment: Stripe webhook, reschedule, cancel.

These live behind a Supabase JWT (or a Stripe signature) and were never exercised:
the table has 0 rows, so `RescheduleFlow` was live UI over a path that could not
succeed. The fake connection below deliberately enforces the real schema rules the
code depends on — the UNIQUE index on `stripe_session_id` and migration 013's
partial unique index on `stripe_event_id` — because those constraints are what made
reschedules fail. A fake that ignores them lets the bug pass, which is exactly what
happened: the first version modelled only `stripe_session_id`, so a *paid*
reschedule stayed broken behind a green test.
"""
import contextlib
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
    """In-memory `bookings` with BOTH unique Stripe indexes enforced.

    Statements are matched by keyword rather than parsed — enough to model the
    reschedule transaction (one UPDATE of the old row, one INSERT of the new).

    Enforcing the indexes is the point of this fake, not incidental detail: a
    fake that let a duplicate through would make a rolled-back reschedule look
    like a success. `stripe_session_id` is UNIQUE outright; `stripe_event_id` is
    UNIQUE only where non-null (migration 013), so NULLs must stay unconstrained
    or every free booking would collide with every other.
    """

    def __init__(self, rows: dict):
        self.rows = rows

    def _session_ids(self, exclude_id=None):
        return {r["stripe_session_id"] for rid, r in self.rows.items() if rid != exclude_id}

    def _event_ids(self, exclude_id=None):
        return {
            r["stripe_event_id"]
            for rid, r in self.rows.items()
            if rid != exclude_id and r.get("stripe_event_id") is not None
        }

    async def fetchrow(self, sql, *args):
        if "WHERE stripe_session_id" in sql:
            row = next(
                (r for r in self.rows.values() if r["stripe_session_id"] == args[0]), None
            )
            return dict(row) if row is not None else None
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
        # The webhook's atomic promotion. `AND status = 'hold'` is the whole point:
        # it must report 0 rows for anything already promoted, which is what makes
        # a duplicate delivery a no-op.
        if s.startswith("UPDATE bookings SET stripe_event_id = $1"):
            row = self.rows[args[2]]
            if row["status"] != "hold":
                return "UPDATE 0"
            if args[0] in self._event_ids(exclude_id=args[2]):
                raise _UniqueViolation(
                    'duplicate key value violates unique constraint '
                    '"idx_bookings_stripe_event_unique"'
                )
            row["stripe_event_id"] = args[0]
            row["stripe_session_id"] = args[1] or row["stripe_session_id"]   # COALESCE
            # Only if the statement actually says so. Hardcoding the promotion here
            # would make a claim that leaves the row on 'hold' look correct — the
            # precise way the first version of this fake hid a live bug.
            if "status = 'confirmed'" in s:
                row["status"] = "confirmed"
            return "UPDATE 1"
        # Cancel's CLAIM: whoever moves the row off a manageable status owns the
        # cancellation. Zero rows means somebody else already did it.
        if s.startswith("UPDATE bookings SET status = 'cancelled', cancelled_at"):
            row = self.rows[args[0]]
            if row["status"] not in args[1]:
                return "UPDATE 0"
            row["status"] = "cancelled"
            return "UPDATE 1"
        # Cancel's final write. Shares a prefix with the webhook outcome below, so
        # it is matched on the columns only cancellation touches.
        if s.startswith("UPDATE bookings SET status = $1") and "cancellation_reason" in s:
            row = self.rows[args[4]]
            row["status"] = args[0]
            row["calendar_event_id"] = None
            return "UPDATE 1"
        # The webhook's calendar-outcome write, on the already-promoted row.
        if s.startswith("UPDATE bookings SET status = $1"):
            row = self.rows[args[3]]
            row["status"], row["calendar_event_id"], row["meet_link"] = args[0], args[1], args[2]
            return "UPDATE 1"
        if s.startswith("UPDATE bookings SET status = 'rescheduled'"):
            row = self.rows[args[0]]
            # A claim, not a blind update: a stale tab must lose here.
            if "status = ANY($2::text[])" in s and row["status"] not in args[1]:
                return "UPDATE 0"
            row["status"] = "rescheduled"
            if "stripe_session_id = 'superseded_'" in s:
                row["stripe_session_id"] = f"superseded_{row['id']}"
            if "stripe_event_id = NULL" in s:
                row["stripe_event_id"] = None
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
            if new["stripe_event_id"] in self._event_ids(exclude_id=new["id"]):
                raise _UniqueViolation(
                    'duplicate key value violates unique constraint '
                    '"idx_bookings_stripe_event_unique"'
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


def test_reschedule_hands_the_stripe_event_id_to_the_new_row(monkeypatch, confirmed_booking):
    """The sibling of the bug above, and it survived the first fix.

    `stripe_event_id` is UNIQUE where non-null (migration 013). Releasing only
    `stripe_session_id` left the event id on BOTH rows, so every *paid*
    reschedule violated that index, rolled the transaction back, and told the
    client a free slot was taken. Free bookings have a NULL event id, which is
    exactly why the earlier test passed while paid reschedules were broken.
    """
    bid, booking = confirmed_booking
    assert booking["stripe_event_id"] == "evt_1", "fixture must model a PAID booking"
    rows = {bid: booking}
    new_slot = (datetime.now(timezone.utc) + timedelta(days=6)).replace(microsecond=0)

    res, conn = _reschedule(monkeypatch, rows, new_slot.isoformat())

    assert res.status_code == 200, res.text

    old = conn.rows[bid]
    new = next(r for rid, r in conn.rows.items() if rid != bid)

    # Released on the superseded row, held by the live one — a Stripe redelivery
    # of evt_1 must resolve to the booking that is actually current.
    assert old["stripe_event_id"] is None
    assert new["stripe_event_id"] == "evt_1"


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


@pytest.mark.asyncio
async def test_a_booking_email_carries_the_calendar_part(monkeypatch):
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

    ok = await es.send_booking_confirmation_email(
            name="Test Person", email="c@example.com", session_type="30",
            slot_start="2026-08-05T13:00:00-07:00",
            meet_link="https://meet.google.com/x", kind="confirmed",
            booking_id="11111111-2222-3333-4444-555555555555", ics_sequence=0,
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


@pytest.mark.asyncio
async def test_no_calendar_part_without_a_stable_uid(monkeypatch):
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

    await es.send_booking_confirmation_email(
        name="T", email="c@example.com", session_type="30",
        slot_start="2026-08-05T13:00:00-07:00", booking_id=None,
    )
    msg = _email.message_from_bytes(base64.urlsafe_b64decode(captured["raw"]))
    assert not [p for p in msg.walk() if p.get_content_type() == "text/calendar"]


# --- Stripe webhook: the paid confirmation path ----------------------------
# This endpoint had no test coverage at all, and it is the one path where a
# mistake costs money that was already taken.

class _FakeStripe:
    """Just enough `stripe` to get past signature verification."""

    def __init__(self, event):
        outer = self

        class Webhook:
            @staticmethod
            def construct_event(_payload, _sig, _secret):
                return outer.event

        self.event = event
        self.Webhook = Webhook


def _held_paid_booking():
    """A paid HOLD awaiting its webhook — what checkout leaves behind."""
    bid = uuid.uuid4()
    start = datetime.now(timezone.utc) + timedelta(days=4)
    return bid, {
        "id": bid,
        "stripe_session_id": "cs_test_paid",
        "stripe_event_id": None,
        "session_type": "30",
        "slot_start": start.replace(microsecond=0),
        "slot_end": (start + timedelta(minutes=30)).replace(microsecond=0),
        "client_name": "Payer",
        "client_email": "payer@example.com",
        "notes": None,
        "status": "hold",
        "amount_cents": 5000,
        "user_id": None,
        "calendar_event_id": None,
        "meet_link": None,
        "rescheduled_from": None,
    }


def _deliver_webhook(monkeypatch, conn, *, session_id="cs_test_paid", event_id="evt_paid_1",
                     booking_id="", calls=None):
    """POST one checkout.session.completed, counting outside side effects."""
    calls = calls if calls is not None else {}
    calls.setdefault("calendar", 0)
    calls.setdefault("emails", [])

    event = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {"object": {"id": session_id, "metadata": {"booking_id": booking_id}}},
    }

    async def get_pool():
        return _FakePool(conn)

    async def calendar(**_kw):
        calls["calendar"] += 1
        return {"event_id": f"cal_{calls['calendar']}", "meet_link": "https://meet/x"}

    async def confirmation(**kwargs):
        calls["emails"].append(kwargs)
        return True

    async def noop(*_a, **_k):
        return True

    monkeypatch.setattr(main, "stripe", _FakeStripe(event))
    monkeypatch.setattr(main, "STRIPE_BOOKING_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(main, "_get_booking_pool", get_pool)
    monkeypatch.setattr(main, "create_booking_event", calendar)
    monkeypatch.setattr(main, "send_booking_confirmation_email", confirmation)
    monkeypatch.setattr(main, "send_admin_booking_alert", noop)
    monkeypatch.setattr(main, "send_booking_notification", noop)
    monkeypatch.setattr(main, "_link_brief_to_booking", noop)

    with TestClient(main.app) as client:
        res = client.post(
            "/api/booking/webhook",
            content=b"{}",
            headers={"Stripe-Signature": "t=1,v1=deadbeef"},
        )
    return res, calls


def test_webhook_confirms_a_paid_hold(monkeypatch):
    bid, booking = _held_paid_booking()
    conn = _FakeConn({bid: booking})

    res, calls = _deliver_webhook(monkeypatch, conn)

    assert res.status_code == 200, res.text
    assert conn.rows[bid]["status"] == "confirmed"
    assert conn.rows[bid]["stripe_event_id"] == "evt_paid_1"
    assert calls["calendar"] == 1
    assert len(calls["emails"]) == 1
    # The paid path must carry the calendar identity a later reschedule moves.
    assert calls["emails"][0]["booking_id"] == str(bid)
    assert calls["emails"][0]["ics_sequence"] == 0


def test_redelivery_of_the_same_event_does_no_outside_work_twice(monkeypatch):
    """Stripe retries on any non-2xx, so redelivery is routine, not exotic.

    The old guard claimed the event by writing stripe_event_id while leaving the
    row on 'hold' — so a second delivery's predicate matched *because* the status
    had not moved, and both deliveries created a calendar event and emailed the
    client. The claim is now the status transition itself.
    """
    bid, booking = _held_paid_booking()
    conn = _FakeConn({bid: booking})

    first, calls = _deliver_webhook(monkeypatch, conn)
    assert first.status_code == 200
    assert calls["calendar"] == 1

    second, calls2 = _deliver_webhook(monkeypatch, conn)

    assert second.status_code == 200          # 200 or Stripe keeps retrying forever
    assert calls2["calendar"] == 0, "duplicate delivery created a second calendar event"
    assert calls2["emails"] == [], "duplicate delivery emailed the client again"
    assert conn.rows[bid]["status"] == "confirmed"


def test_a_different_event_cannot_reconfirm_the_same_booking(monkeypatch):
    """Two distinct events for one booking: the second must not redo the work.

    Migration 013 cannot catch this on its own — the second event id is unique —
    so the 'hold' predicate is the only thing standing between the client and a
    second calendar invite.
    """
    bid, booking = _held_paid_booking()
    conn = _FakeConn({bid: booking})

    _deliver_webhook(monkeypatch, conn, event_id="evt_paid_1")
    _res, calls = _deliver_webhook(monkeypatch, conn, event_id="evt_paid_2")

    assert calls["calendar"] == 0
    assert calls["emails"] == []
    assert conn.rows[bid]["stripe_event_id"] == "evt_paid_1"


def test_webhook_replaces_the_pending_session_placeholder(monkeypatch):
    """Checkout writes 'pending_<uuid>' first and overwrites it after Stripe
    replies. If that overwrite failed, the row kept the placeholder — and then
    confirmation polling by the real session id 404s and cancel cannot find the
    payment to refund. The webhook is the second chance to write it."""
    bid, booking = _held_paid_booking()
    booking["stripe_session_id"] = f"pending_{bid}"
    conn = _FakeConn({bid: booking})

    # No row matches the real session id, so the handler falls back to the
    # booking_id carried in the event metadata.
    res, _calls = _deliver_webhook(
        monkeypatch, conn, session_id="cs_live_real", booking_id=str(bid)
    )

    assert res.status_code == 200, res.text
    assert conn.rows[bid]["stripe_session_id"] == "cs_live_real"
    assert conn.rows[bid]["status"] == "confirmed"


def test_webhook_asks_stripe_to_retry_when_there_is_no_database(monkeypatch):
    """200 here told Stripe 'handled' and it never retried — a paid booking lost."""
    async def no_pool():
        return None

    monkeypatch.setattr(main, "stripe", _FakeStripe(
        {"id": "evt_x", "type": "checkout.session.completed",
         "data": {"object": {"id": "cs_x", "metadata": {}}}}))
    monkeypatch.setattr(main, "STRIPE_BOOKING_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(main, "_get_booking_pool", no_pool)

    with TestClient(main.app) as client:
        res = client.post("/api/booking/webhook", content=b"{}",
                          headers={"Stripe-Signature": "t=1,v1=x"})

    assert res.status_code >= 500, "Stripe only redelivers on a non-2xx"


class _AbruptDeath(BaseException):
    """Not an Exception, so the handler's `except Exception` cannot swallow it —
    stands in for the process dying mid-flight (OOM, SIGKILL, deploy restart)."""


def test_a_crash_after_payment_never_leaves_the_booking_on_hold(monkeypatch):
    """The property that makes the promotion order matter.

    The money is already taken. If the row is still 'hold' when the process dies,
    the stale-hold sweep expires it 30 minutes later and the paid booking is gone
    silently — the worst outcome in the system. Promoting the ledger *before* the
    calendar call means a crash can cost the calendar event or the email, but
    never the booking itself.

    The old order (claim the event id, keep 'hold', promote after the calendar
    call) fails this: the row dies on 'hold' and gets swept.
    """
    bid, booking = _held_paid_booking()
    conn = _FakeConn({bid: booking})

    async def die(**_kw):
        raise _AbruptDeath("process died between promotion and outcome write")

    async def get_pool():
        return _FakePool(conn)

    async def noop(*_a, **_k):
        return True

    monkeypatch.setattr(main, "stripe", _FakeStripe(
        {"id": "evt_crash", "type": "checkout.session.completed",
         "data": {"object": {"id": "cs_test_paid", "metadata": {}}}}))
    monkeypatch.setattr(main, "STRIPE_BOOKING_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(main, "_get_booking_pool", get_pool)
    monkeypatch.setattr(main, "create_booking_event", die)
    monkeypatch.setattr(main, "send_booking_confirmation_email", noop)
    monkeypatch.setattr(main, "send_admin_booking_alert", noop)
    monkeypatch.setattr(main, "send_booking_notification", noop)
    monkeypatch.setattr(main, "_link_brief_to_booking", noop)

    # The request dies. TestClient's portal repackages a BaseException as
    # CancelledError, so swallow whatever comes out — the row state is the assertion.
    with contextlib.suppress(BaseException):
        with TestClient(main.app) as client:
            client.post("/api/booking/webhook", content=b"{}",
                        headers={"Stripe-Signature": "t=1,v1=x"})

    assert conn.rows[bid]["status"] != "hold", (
        "a paid booking left on 'hold' is swept to 'expired' and lost"
    )
    assert conn.rows[bid]["status"] == "confirmed"
    assert conn.rows[bid]["stripe_event_id"] == "evt_crash"


# --- Reachable only once a Google Calendar is connected -------------------
# `calendar_failed` cannot occur while no calendar exists (create_booking_event
# no-ops). These pin the behaviour before credentials are mounted, because the
# first Google hiccup after that produces exactly these rows.

def test_a_calendar_failed_booking_can_still_be_cancelled(monkeypatch, confirmed_booking):
    """BookingCard shows calendar_failed as "Confirmed". Refusing to cancel it
    handed the client a green badge over a button that returned
    "Cannot cancel booking with status 'calendar_failed'"."""
    bid, booking = confirmed_booking
    booking["status"] = "calendar_failed"
    conn = _FakeConn({bid: booking})

    async def get_pool():
        return _FakePool(conn)

    async def noop(*_a, **_k):
        return True

    monkeypatch.setattr(main, "_get_booking_pool", get_pool)
    monkeypatch.setattr(main, "delete_booking_event", noop)
    monkeypatch.setattr(main, "send_booking_notification", noop)
    monkeypatch.setattr(main, "send_booking_confirmation_email", noop)
    monkeypatch.setattr(main, "send_admin_booking_alert", noop)
    monkeypatch.setattr(main, "stripe", None)

    main.app.dependency_overrides[main.require_auth] = lambda: OWNER
    try:
        with TestClient(main.app) as client:
            res = client.post(f"/api/booking/{bid}/cancel", json={"reason": "no longer needed"})
    finally:
        main.app.dependency_overrides.clear()

    assert res.status_code == 200, res.text
    assert conn.rows[bid]["status"] in ("cancelled", "refunded")


def test_a_calendar_failed_booking_can_still_be_rescheduled(monkeypatch, confirmed_booking):
    bid, booking = confirmed_booking
    booking["status"] = "calendar_failed"
    rows = {bid: booking}
    new_slot = (datetime.now(timezone.utc) + timedelta(days=6)).replace(microsecond=0)

    res, conn = _reschedule(monkeypatch, rows, new_slot.isoformat())

    assert res.status_code == 200, res.text
    assert conn.rows[bid]["status"] == "rescheduled"


def test_a_stale_tab_cannot_reschedule_the_same_booking_twice(monkeypatch, confirmed_booking):
    """Two attempts, one live booking — never two of Yanqing's hours for one client."""
    bid, booking = confirmed_booking
    rows = {bid: booking}
    first = (datetime.now(timezone.utc) + timedelta(days=6)).replace(microsecond=0)

    res1, conn = _reschedule(monkeypatch, rows, first.isoformat())
    assert res1.status_code == 200

    second = (datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0)
    res2, conn2 = _reschedule(monkeypatch, conn.rows, second.isoformat())

    assert res2.status_code == 400, res2.text
    live = [r for r in conn2.rows.values() if r["status"] == "confirmed"]
    assert len(live) == 1, f"expected exactly one live booking, got {len(live)}"


@pytest.mark.asyncio
async def test_the_superseding_update_is_a_claim_not_a_blind_write(confirmed_booking):
    """The guard above is a read-then-act, so it only stops a *sequential* second
    attempt. Under real concurrency both requests pass it and the SQL predicate is
    the only thing left — so assert the predicate directly, which the endpoint
    test above cannot reach single-threaded.
    """
    bid, booking = confirmed_booking
    booking["status"] = "rescheduled"          # already superseded by a rival
    conn = _FakeConn({bid: booking})

    tag = await conn.execute(
        """
        UPDATE bookings
        SET status = 'rescheduled',
            stripe_session_id = 'superseded_' || id::text,
            stripe_event_id = NULL,
            updated_at = NOW()
        WHERE id = $1 AND status = ANY($2::text[])
        """,
        bid, list(main.MANAGEABLE_STATUSES),
    )

    assert tag.strip().endswith(" 0"), "the loser of a concurrent reschedule must claim nothing"


def test_a_failed_calendar_delete_alerts_the_owner(monkeypatch, confirmed_booking):
    """The ledger is right and the client was told the truth, but Google still
    shows the meeting. Silence there means Yanqing holds an hour for a call that
    is not happening."""
    bid, booking = confirmed_booking
    booking["calendar_event_id"] = "evt_google_123"
    conn = _FakeConn({bid: booking})
    alerts: list[dict] = []

    async def get_pool():
        return _FakePool(conn)

    async def boom(*_a, **_k):
        raise RuntimeError("google says 500")

    async def capture_alert(**kwargs):
        alerts.append(kwargs)
        return True

    async def noop(*_a, **_k):
        return True

    monkeypatch.setattr(main, "_get_booking_pool", get_pool)
    monkeypatch.setattr(main, "delete_booking_event", boom)
    monkeypatch.setattr(main, "send_admin_booking_alert", capture_alert)
    monkeypatch.setattr(main, "send_booking_notification", noop)
    monkeypatch.setattr(main, "send_booking_confirmation_email", noop)
    monkeypatch.setattr(main, "stripe", None)

    main.app.dependency_overrides[main.require_auth] = lambda: OWNER
    try:
        with TestClient(main.app) as client:
            res = client.post(f"/api/booking/{bid}/cancel", json={})
    finally:
        main.app.dependency_overrides.clear()

    # The cancellation still succeeds — failing it would tell the client their
    # cancellation did not happen, which is false.
    assert res.status_code == 200, res.text
    assert conn.rows[bid]["status"] in ("cancelled", "refunded")

    assert len(alerts) == 1, "a stale calendar event was suppressed silently"
    reason = alerts[0]["failure_reason"]
    assert "evt_google_123" in reason
    assert "your calendar" in reason
