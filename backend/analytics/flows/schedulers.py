from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Mapping


class FlowMode(str, Enum):
    DIRECT = "direct"
    SINGLE_AGENT = "single_agent"
    MULTI_AGENT = "multi_agent"


@dataclass(frozen=True)
class ModeConfig:
    name: FlowMode
    parallelism_enabled: bool
    accessories_in_critical_path: bool
    deterministic_badge: str
    accessory_strategy: str
    allow_hedging: bool
    delta_accessories: bool


_MODE_CONFIGS: Mapping[FlowMode, ModeConfig] = {
    FlowMode.DIRECT: ModeConfig(
        name=FlowMode.DIRECT,
        parallelism_enabled=False,
        accessories_in_critical_path=False,
        deterministic_badge="Deterministic",
        accessory_strategy="post_analysis",
        allow_hedging=False,
        delta_accessories=True,
    ),
    FlowMode.SINGLE_AGENT: ModeConfig(
        name=FlowMode.SINGLE_AGENT,
        parallelism_enabled=True,
        accessories_in_critical_path=True,
        deterministic_badge="Concurrent",
        accessory_strategy="pre_analysis_fanout",
        allow_hedging=False,
        delta_accessories=True,
    ),
    FlowMode.MULTI_AGENT: ModeConfig(
        name=FlowMode.MULTI_AGENT,
        parallelism_enabled=True,
        accessories_in_critical_path=True,
        deterministic_badge="Supervisor",
        accessory_strategy="specialist_parallel",
        allow_hedging=True,
        delta_accessories=True,
    ),
}


def get_mode_config(mode: FlowMode) -> ModeConfig:
    try:
        return _MODE_CONFIGS[mode]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unknown flow mode: {mode}") from exc


def apply_mode_metadata(event: Dict[str, Any], mode: FlowMode) -> Dict[str, Any]:
    """Annotate an SSE payload with mode metadata."""
    if not isinstance(event, dict):
        return event
    data = event.setdefault("data", {})
    if not isinstance(data, dict):
        # Avoid mutating non-dict payloads; attach at top-level.
        event["mode"] = mode.value
        return event
    data.setdefault("mode", mode.value)
    config = get_mode_config(mode)
    badges = data.setdefault("badges", {})
    if isinstance(badges, dict):
        badges.setdefault("mode", config.deterministic_badge)
        if config.allow_hedging:
            badges.setdefault("hedging", "enabled")
    data.setdefault("accessory_strategy", config.accessory_strategy)
    if config.delta_accessories:
        data.setdefault("supports_deltas", True)
    return event
