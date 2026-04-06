"""Deterministic BaZi (Four Pillars) computation using cnlunar."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import cnlunar
from agents import function_tool
from pydantic import BaseModel, Field


STEM_TO_ELEMENT = {
    "甲": "wood", "乙": "wood",
    "丙": "fire", "丁": "fire",
    "戊": "earth", "己": "earth",
    "庚": "metal", "辛": "metal",
    "壬": "water", "癸": "water",
}

BRANCH_TO_ELEMENT = {
    "子": "water", "丑": "earth", "寅": "wood", "卯": "wood",
    "辰": "earth", "巳": "fire", "午": "fire", "未": "earth",
    "申": "metal", "酉": "metal", "戌": "earth", "亥": "water",
}

FIVE_ELEMENTS = ("wood", "fire", "earth", "metal", "water")


class Pillar(BaseModel):
    raw: str
    stem: str
    branch: str
    stem_element: str
    branch_element: str


class BaziChart(BaseModel):
    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar | None
    day_master: str
    day_master_element: str
    birth_time_unknown: bool = False
    raw_element_counts: dict[str, int]
    zodiac: str | None = None
    table_columns: list[str] = Field(default_factory=list)
    table_rows: list[dict[str, str]] = Field(default_factory=list)


def _normalize_dt(birth_iso: str, timezone: str) -> datetime:
    """Convert to local time in the given timezone, return naive datetime.

    cnlunar expects a naive datetime in the local timezone of birth.
    """
    parsed = datetime.fromisoformat(birth_iso)
    if parsed.tzinfo is None:
        # Assume already in the target timezone
        return parsed
    # Convert to target timezone, then strip tzinfo for cnlunar
    return parsed.astimezone(ZoneInfo(timezone)).replace(tzinfo=None)


def _parse_pillar(raw_value: str) -> Pillar:
    raw_value = (raw_value or "").strip()
    if len(raw_value) < 2:
        raise ValueError(f"Unexpected pillar value: {raw_value!r}")
    stem, branch = raw_value[0], raw_value[1]
    return Pillar(
        raw=raw_value,
        stem=stem,
        branch=branch,
        stem_element=STEM_TO_ELEMENT[stem],
        branch_element=BRANCH_TO_ELEMENT[branch],
    )


def _count_elements(*pillars: Pillar | None) -> dict[str, int]:
    counts = {e: 0 for e in FIVE_ELEMENTS}
    for p in pillars:
        if p is None:
            continue
        counts[p.stem_element] += 1
        counts[p.branch_element] += 1
    return counts


def compute_bazi_chart(
    birth_iso: str,
    timezone: str = "UTC",
    birth_time_unknown: bool = False,
) -> dict[str, Any]:
    """Compute Four Pillars and raw element counts from a birth timestamp.

    Plain callable for direct import/testing. The Agents SDK wrapper is
    exposed separately as ``compute_bazi_chart_tool``.
    """
    local_dt = _normalize_dt(birth_iso, timezone)
    lunar = cnlunar.Lunar(local_dt, godType="8char")

    year = _parse_pillar(str(lunar.year8Char))
    month = _parse_pillar(str(lunar.month8Char))
    day = _parse_pillar(str(lunar.day8Char))
    hour = None if birth_time_unknown else _parse_pillar(str(lunar.twohour8Char))

    raw_element_counts = _count_elements(year, month, day, hour)

    pillars_list = [year, month, day] + ([] if hour is None else [hour])
    payload = BaziChart(
        year=year,
        month=month,
        day=day,
        hour=hour,
        day_master=day.stem,
        day_master_element=day.stem_element,
        birth_time_unknown=birth_time_unknown,
        raw_element_counts=raw_element_counts,
        zodiac=getattr(lunar, "zodiac", None),
        table_columns=["pillar", "stem", "branch", "raw"],
        table_rows=[
            {"pillar": p_name, "stem": p.stem, "branch": p.branch, "raw": p.raw}
            for p_name, p in zip(["year", "month", "day", "hour"], pillars_list)
        ],
    )
    return payload.model_dump()


compute_bazi_chart_tool = function_tool(
    compute_bazi_chart,
    name_override="compute_bazi_chart",
    description_override=(
        "Compute a BaZi (Four Pillars) chart and raw five-element counts "
        "from a birth ISO timestamp and IANA timezone."
    ),
)
