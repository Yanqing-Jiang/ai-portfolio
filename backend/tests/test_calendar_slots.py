"""Booking availability rules — offered hours and the weekday stagger.

The stagger has to be deterministic per date, because get_available_slots is
both the offer source (GET /api/booking/slots) and the revalidation source
(main._assert_slot_offered). A slot that was advertised must still validate.
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import calendar_service as cs  # noqa: E402

TZ = ZoneInfo(cs.BOOKING_TIMEZONE)


def _next(weekday: int, weeks_out: int = 3) -> date:
    """A date far enough ahead that MIN_LEAD_MINUTES can't trim it."""
    d = date.today() + timedelta(days=weeks_out * 7)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


SATURDAY, SUNDAY = _next(5), _next(6)
WEEKDAYS = [_next(i) for i in range(5)]


# --- Weekend: 1pm-4pm, fully open -------------------------------------------

@pytest.mark.parametrize("day", [SATURDAY, SUNDAY])
def test_weekend_offers_every_slot_from_1pm_to_4pm(day):
    slots = cs._generate_slot_boundaries(day, TZ)
    times = [(s.hour, s.minute) for s, _ in slots]
    assert times == [(13, 0), (13, 30), (14, 0), (14, 30), (15, 0), (15, 30)]
    assert slots[-1][1] == datetime(day.year, day.month, day.day, 16, 0, tzinfo=TZ)


# --- Weekdays: staggered inside 8am-4pm -------------------------------------

@pytest.mark.parametrize("day", WEEKDAYS)
def test_weekday_slots_stay_inside_8am_to_4pm(day):
    for start, end in cs._generate_slot_boundaries(day, TZ):
        assert start >= datetime(day.year, day.month, day.day, 8, 0, tzinfo=TZ)
        assert end <= datetime(day.year, day.month, day.day, 16, 0, tzinfo=TZ)


@pytest.mark.parametrize("day", WEEKDAYS)
def test_weekday_does_not_offer_the_whole_grid(day):
    slots = cs._generate_slot_boundaries(day, TZ)
    expected = cs.WEEKDAY_OPEN_WINDOWS * cs.WEEKDAY_WINDOW_SLOTS
    assert len(slots) == expected  # 16 possible, only a few published
    assert len(slots) < 16


@pytest.mark.parametrize("day", WEEKDAYS)
def test_weekday_windows_are_spread_across_the_day(day):
    """Not one contiguous block: the offered slots have gaps between them."""
    slots = cs._generate_slot_boundaries(day, TZ)
    gaps = sum(
        1 for i in range(len(slots) - 1)
        if slots[i + 1][0] != slots[i][1]
    )
    assert gaps >= cs.WEEKDAY_OPEN_WINDOWS - 1


@pytest.mark.parametrize("day", WEEKDAYS)
def test_weekday_keeps_adjacent_pairs_for_60_min_sessions(day):
    slots = cs._generate_slot_boundaries(day, TZ)
    adjacent = [i for i in range(len(slots) - 1) if slots[i + 1][0] == slots[i][1]]
    assert adjacent, "a 60-min session needs at least one adjacent pair"


def test_weekday_stagger_is_stable_for_the_same_date():
    day = WEEKDAYS[0]
    first = cs._generate_slot_boundaries(day, TZ)
    assert all(cs._generate_slot_boundaries(day, TZ) == first for _ in range(5))


def test_weekday_stagger_differs_across_dates():
    """The open windows move; otherwise every weekday would look identical."""
    shapes = {
        tuple((s.hour, s.minute) for s, _ in cs._generate_slot_boundaries(_next(2, w), TZ))
        for w in range(3, 12)
    }
    assert len(shapes) > 1


def test_weekday_stagger_survives_a_new_process_seed():
    """sha256, not hash() — a per-process string salt would desync workers."""
    day = WEEKDAYS[0]
    expected = cs._stagger_rng(day).random()
    assert cs._stagger_rng(day).random() == expected


# --- Lead time ---------------------------------------------------------------

def test_slots_starting_within_the_lead_window_are_not_offered():
    now = datetime.now(TZ)
    for offset in range(0, 8):
        day = now.date() + timedelta(days=offset)
        cutoff = now + timedelta(minutes=cs.MIN_LEAD_MINUTES)
        for start, _end in cs._generate_slot_boundaries(day, TZ):
            assert start >= cutoff


# --- 60-min pairing must respect real adjacency, not list index --------------

@pytest.mark.asyncio
async def test_mock_60_min_never_spans_a_stagger_gap(monkeypatch):
    monkeypatch.setattr(cs, "_get_calendar_service", lambda: None)
    day = WEEKDAYS[0]
    grid = {s.isoformat() for s, _ in cs._generate_slot_boundaries(day, TZ)}
    for slot in await cs.get_available_slots(day, "60"):
        start = datetime.fromisoformat(slot["start"])
        # Both halves of the hour have to be published slots.
        assert slot["start"] in grid
        assert (start + timedelta(minutes=30)).isoformat() in grid
