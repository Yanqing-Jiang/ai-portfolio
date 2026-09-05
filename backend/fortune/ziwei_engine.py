"""Local Zi Wei Dou Shu chart adapter; no model or remote service involved."""

from __future__ import annotations

import logging
from typing import Any

from iztro_py import astro

from .calendar_tool import _normalize_dt


def compute_ziwei_chart(
    birth_iso: str, timezone: str, gender: str, birth_time_unknown: bool = False,
) -> dict[str, Any]:
    provenance = {
        "engine": "iztro-py", "version": "0.5.0",
        "conventions": {
            "time": "local civil time; no longitude/true-solar correction",
            "late_zi": "23:00 uses time index 12; early Zi uses index 0",
            "leap_month": "fix_leap=True (library split-month convention)",
            "decadal_age": "traditional nominal age; not birthday age",
        },
    }
    if birth_time_unknown or gender.lower() not in {"male", "female"}:
        return {
            **provenance, "status": "unavailable",
            "reason": "birth_time_unknown" if birth_time_unknown else "gender_unknown",
            "palaces": [],
        }
    local = _normalize_dt(birth_iso, timezone)
    time_index = (local.hour + 1) // 2
    try:
        chart = astro.by_solar(
            local.date().isoformat(), time_index,
            "男" if gender.lower() == "male" else "女",
            fix_leap=True, language="en-US",
        )
        palaces = []
        for palace in chart.palaces:
            palaces.append({
                "index": palace.index,
                "name": palace.translate_name("en-US"),
                "key": palace.name,
                "branch": palace.translate_earthly_branch("en-US"),
                "stem": palace.translate_heavenly_stem("en-US"),
                "is_body_palace": palace.is_body_palace,
                "major_stars": [s.model_dump(mode="json") for s in palace.major_stars],
                "minor_stars": [s.model_dump(mode="json") for s in palace.minor_stars],
                "decadal_nominal_ages": list(palace.decadal.range),
                "related_palace_indices": [(palace.index + n) % 12 for n in (4, 8, 6)],
            })
        return {
            **provenance, "status": "computed", "time_index": time_index,
            "five_elements_class": chart.five_elements_class,
            "palaces": palaces,
            "limits": [
                "Natal placements and decadal nominal ages only; no annual/monthly Zi Wei transits computed.",
                "Classical reference corpus is Bazi-only; never cite it as a Zi Wei source.",
            ],
        }
    except Exception as exc:
        logging.getLogger(__name__).warning("Zi Wei calculation unavailable: %s", type(exc).__name__)
        return {**provenance, "status": "unavailable", "reason": "engine_error", "palaces": []}
