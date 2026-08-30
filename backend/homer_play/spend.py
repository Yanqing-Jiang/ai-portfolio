from __future__ import annotations

import asyncio
import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo


logger = logging.getLogger(__name__)

MICRO_USD = 1_000_000
PACIFIC = ZoneInfo("America/Los_Angeles")

RESERVATION_MICROS = {
    "memory.search": 20,
    "memory.extract_dry_run": 1_500,
    "scheduler.query": 500,
    "web.activity": 0,
    "executors.route_and_answer": 0,
    "mcp.list_tools": 0,
    "mcp.call_tool": 0,
    "voice.synthesize": 25_000,
}

RESERVE_SCRIPT = """
local existing = redis.call('GET', KEYS[2])
if existing then
  local state, maximum, action = string.match(existing, '([^:]+):(%d+):([^:]+)')
  if (state == 'reserved' or state == 'finalized') and action == ARGV[4] and tonumber(maximum) == tonumber(ARGV[1]) then
    return {1, tonumber(redis.call('GET', KEYS[1]) or '0'), tonumber(maximum), 1}
  end
  return {0, tonumber(redis.call('GET', KEYS[1]) or '0'), 0, 2}
end
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local maximum = tonumber(ARGV[1])
local cap = tonumber(ARGV[2])
if current + maximum > cap then
  return {0, current, 0, 0}
end
redis.call('SET', KEYS[2], 'reserved:' .. maximum .. ':' .. ARGV[4], 'EX', ARGV[3], 'NX')
local updated = redis.call('INCRBY', KEYS[1], maximum)
redis.call('EXPIRE', KEYS[1], ARGV[3])
return {1, updated, maximum, 0}
"""

VOICE_RESERVE_SCRIPT = """
local existing = redis.call('GET', KEYS[2])
if existing then
  local state, maximum, action = string.match(existing, '([^:]+):(%d+):([^:]+)')
  if (state == 'reserved' or state == 'finalized') and action == ARGV[5] and tonumber(maximum) == tonumber(ARGV[1]) then
    return {1, tonumber(redis.call('GET', KEYS[1]) or '0'), tonumber(maximum), 1, tonumber(redis.call('GET', KEYS[3]) or '0')}
  end
  return {0, tonumber(redis.call('GET', KEYS[1]) or '0'), 0, 2, tonumber(redis.call('GET', KEYS[3]) or '0')}
end
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local voice_current = tonumber(redis.call('GET', KEYS[3]) or '0')
local maximum = tonumber(ARGV[1])
if current + maximum > tonumber(ARGV[2]) then
  return {0, current, 0, 0, voice_current}
end
if voice_current + maximum > tonumber(ARGV[3]) then
  return {0, current, 0, 3, voice_current}
end
redis.call('SET', KEYS[2], 'reserved:' .. maximum .. ':' .. ARGV[5], 'EX', ARGV[4], 'NX')
local updated = redis.call('INCRBY', KEYS[1], maximum)
local voice_updated = redis.call('INCRBY', KEYS[3], maximum)
redis.call('EXPIRE', KEYS[1], ARGV[4])
redis.call('EXPIRE', KEYS[3], ARGV[4])
return {1, updated, maximum, 0, voice_updated}
"""

FINALIZE_SCRIPT = """
local existing = redis.call('GET', KEYS[2])
if not existing then
  return {0, tonumber(redis.call('GET', KEYS[1]) or '0'), 0}
end
local state, maximum, tab = string.match(existing, '([^:]+):(%d+):(.+)')
maximum = tonumber(maximum)
if state == 'finalized' then
  local actual = tonumber(string.match(existing, '^finalized:%d+:[^:]+:(%d+)$') or maximum)
  return {1, tonumber(redis.call('GET', KEYS[1]) or '0'), actual}
end
local actual = math.min(tonumber(ARGV[1]), maximum)
local refund = maximum - actual
if refund > 0 then redis.call('DECRBY', KEYS[1], refund) end
redis.call('EXPIRE', KEYS[1], ARGV[2])
redis.call('INCRBY', KEYS[3], actual)
redis.call('EXPIRE', KEYS[3], ARGV[2])
redis.call('SET', KEYS[2], 'finalized:' .. maximum .. ':' .. tab .. ':' .. actual, 'EX', ARGV[2])
return {1, tonumber(redis.call('GET', KEYS[1]) or '0'), actual}
"""

VOICE_FINALIZE_SCRIPT = """
local existing = redis.call('GET', KEYS[2])
if not existing then
  return {0, tonumber(redis.call('GET', KEYS[1]) or '0'), 0}
end
local state, maximum, tab = string.match(existing, '([^:]+):(%d+):(.+)')
maximum = tonumber(maximum)
if state == 'finalized' then
  local actual = tonumber(string.match(existing, '^finalized:%d+:[^:]+:(%d+)$') or maximum)
  return {1, tonumber(redis.call('GET', KEYS[1]) or '0'), actual}
end
local actual = math.min(tonumber(ARGV[1]), maximum)
local refund = maximum - actual
if refund > 0 then
  redis.call('DECRBY', KEYS[1], refund)
  redis.call('DECRBY', KEYS[4], refund)
end
redis.call('EXPIRE', KEYS[1], ARGV[2])
redis.call('EXPIRE', KEYS[4], ARGV[2])
redis.call('INCRBY', KEYS[3], actual)
redis.call('EXPIRE', KEYS[3], ARGV[2])
redis.call('SET', KEYS[2], 'finalized:' .. maximum .. ':' .. tab .. ':' .. actual, 'EX', ARGV[2])
return {1, tonumber(redis.call('GET', KEYS[1]) or '0'), actual}
"""


@dataclass(frozen=True)
class SpendReservation:
    allowed: bool
    request_id: str
    action: str
    date: str
    reserved_micro_usd: int
    total_micro_usd: int
    reason: str | None = None


def usd_to_micro(value: str | float | Decimal) -> int:
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid USD value") from exc
    if amount < 0:
        raise ValueError("USD value cannot be negative")
    return int((amount * MICRO_USD).to_integral_value())


def micro_to_usd(value: int) -> float:
    return float(Decimal(value) / Decimal(MICRO_USD))


def daily_cap_micro() -> int:
    value = usd_to_micro(os.getenv("HOMER_PLAY_DAILY_CAP_USD", "2.0"))
    if value <= 0:
        raise ValueError("HOMER_PLAY_DAILY_CAP_USD must be positive")
    return value


def voice_daily_cap_micro() -> int:
    value = usd_to_micro(os.getenv("HOMER_PLAY_VOICE_DAILY_CAP_USD", "1.20"))
    if value <= 0:
        raise ValueError("HOMER_PLAY_VOICE_DAILY_CAP_USD must be positive")
    return value


def _day_and_ttl(now: datetime | None = None) -> tuple[str, int]:
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(PACIFIC)
    next_date = local.date() + timedelta(days=1)
    next_midnight = datetime.combine(next_date, dt_time.min, tzinfo=PACIFIC)
    ttl = max(1, math.ceil((next_midnight.astimezone(timezone.utc) - now).total_seconds()) + 3600)
    return local.date().isoformat(), ttl


class SpendLedger:
    def __init__(self, redis_client: Any = None, *, allow_in_memory: bool | None = None) -> None:
        self.redis_client = redis_client
        self.allow_in_memory = (
            os.getenv("ENVIRONMENT", "development").lower() != "production"
            if allow_in_memory is None
            else allow_in_memory
        )
        self._lock = asyncio.Lock()
        self._totals: dict[str, int] = {}
        self._voice_totals: dict[str, int] = {}
        self._reservations: dict[tuple[str, str], dict[str, Any]] = {}
        self._warned: dict[str, set[int]] = {}

    @staticmethod
    def _keys(day: str, request_id: str, action: str) -> tuple[str, str, str]:
        tab = action.split(".", 1)[0]
        return (
            f"homer-play:spend:v1:{day}",
            f"homer-play:spend-reservation:v1:{day}:{request_id}",
            f"homer-play:spend-actual:v1:{day}:{tab}",
        )

    @staticmethod
    def _voice_key(day: str) -> str:
        return f"homer-play:spend-voice:v1:{day}"

    def _warn_thresholds(self, day: str, previous: int, current: int, cap: int) -> None:
        warned = self._warned.setdefault(day, set())
        for threshold in (50, 80, 100):
            boundary = math.ceil(cap * threshold / 100)
            if previous < boundary <= current and threshold not in warned:
                warned.add(threshold)
                logger.warning("Homer play daily spend ledger reached %d%% of cap", threshold)

    async def reserve(
        self,
        action: str,
        request_id: str,
        *,
        max_micro_usd: int | None = None,
        now: datetime | None = None,
    ) -> SpendReservation:
        maximum = RESERVATION_MICROS[action] if max_micro_usd is None else max_micro_usd
        day, ttl = _day_and_ttl(now)
        cap = daily_cap_micro()
        is_voice = action == "voice.synthesize"
        if maximum <= 0:
            return SpendReservation(True, request_id, action, day, 0, 0)

        if self.redis_client is not None:
            keys = self._keys(day, request_id, action)
            try:
                if is_voice:
                    result = await self.redis_client.eval(
                        VOICE_RESERVE_SCRIPT,
                        3,
                        keys[0],
                        keys[1],
                        self._voice_key(day),
                        maximum,
                        cap,
                        voice_daily_cap_micro(),
                        ttl,
                        action,
                    )
                else:
                    result = await self.redis_client.eval(
                        RESERVE_SCRIPT,
                        2,
                        keys[0],
                        keys[1],
                        maximum,
                        cap,
                        ttl,
                        action,
                    )
                allowed, total, reserved, idempotency_state = (int(item) for item in result[:4])
                previous = max(0, total - reserved)
                if allowed:
                    self._warn_thresholds(day, previous, total, cap)
                return SpendReservation(
                    bool(allowed), request_id, action, day, reserved, total,
                    None if allowed else (
                        "reservation_conflict"
                        if idempotency_state == 2
                        else "voice_daily_cap"
                        if idempotency_state == 3
                        else "daily_spend_cap"
                    ),
                )
            except Exception as exc:
                logger.warning("Homer play spend ledger Redis unavailable: %s", type(exc).__name__)
                if not self.allow_in_memory:
                    return SpendReservation(False, request_id, action, day, 0, 0, "rate_backend_unavailable")

        if not self.allow_in_memory:
            return SpendReservation(False, request_id, action, day, 0, 0, "rate_backend_unavailable")

        async with self._lock:
            key = (day, request_id)
            existing = self._reservations.get(key)
            if existing:
                if existing["action"] != action or int(existing["maximum"]) != maximum:
                    return SpendReservation(
                        False, request_id, action, day, 0, self._totals.get(day, 0), "reservation_conflict"
                    )
                return SpendReservation(
                    True,
                    request_id,
                    action,
                    day,
                    int(existing["maximum"]),
                    self._totals.get(day, 0),
                )
            previous = self._totals.get(day, 0)
            if previous + maximum > cap:
                return SpendReservation(False, request_id, action, day, 0, previous, "daily_spend_cap")
            if is_voice and self._voice_totals.get(day, 0) + maximum > voice_daily_cap_micro():
                return SpendReservation(False, request_id, action, day, 0, previous, "voice_daily_cap")
            current = previous + maximum
            self._totals[day] = current
            if is_voice:
                self._voice_totals[day] = self._voice_totals.get(day, 0) + maximum
            self._reservations[key] = {"maximum": maximum, "action": action, "actual": None}
            self._warn_thresholds(day, previous, current, cap)
            return SpendReservation(True, request_id, action, day, maximum, current)

    async def finalize(
        self,
        reservation: SpendReservation,
        actual_micro_usd: int | None,
        *,
        now: datetime | None = None,
    ) -> int:
        if not reservation.allowed or reservation.reserved_micro_usd <= 0:
            return 0
        actual = reservation.reserved_micro_usd if actual_micro_usd is None else max(0, actual_micro_usd)
        actual = min(actual, reservation.reserved_micro_usd)
        _day, ttl = _day_and_ttl(now)

        if self.redis_client is not None:
            keys = self._keys(reservation.date, reservation.request_id, reservation.action)
            try:
                if reservation.action == "voice.synthesize":
                    result = await self.redis_client.eval(
                        VOICE_FINALIZE_SCRIPT,
                        4,
                        keys[0],
                        keys[1],
                        keys[2],
                        self._voice_key(reservation.date),
                        actual,
                        ttl,
                    )
                else:
                    result = await self.redis_client.eval(
                        FINALIZE_SCRIPT,
                        3,
                        keys[0],
                        keys[1],
                        keys[2],
                        actual,
                        ttl,
                    )
                return int(result[2])
            except Exception as exc:
                logger.warning("Homer play spend finalization Redis unavailable: %s", type(exc).__name__)
                # Reservation remains fully charged on an unknown Redis outcome.
                return reservation.reserved_micro_usd

        async with self._lock:
            key = (reservation.date, reservation.request_id)
            existing = self._reservations.get(key)
            if not existing:
                return 0
            if existing["actual"] is not None:
                return int(existing["actual"])
            maximum = int(existing["maximum"])
            actual = min(actual, maximum)
            self._totals[reservation.date] = max(0, self._totals.get(reservation.date, 0) - (maximum - actual))
            if reservation.action == "voice.synthesize":
                self._voice_totals[reservation.date] = max(
                    0,
                    self._voice_totals.get(reservation.date, 0) - (maximum - actual),
                )
            existing["actual"] = actual
            return actual


def estimate_gemini_micro(input_tokens: int, output_tokens: int, maximum: int) -> int:
    # Rates documented in the architecture source: $0.25/M input and $1/M output.
    estimated = math.ceil((input_tokens * Decimal("0.25")) + (output_tokens * Decimal("1.0")))
    return min(maximum, max(0, int(estimated)))


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def estimate_voice_micro(characters: int) -> int:
    if characters < 0:
        raise ValueError("character count cannot be negative")
    return characters * 300
