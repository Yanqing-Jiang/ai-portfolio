from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Set

DEFAULT_DELEGATION_POLICIES: Dict[str, Dict[str, Any]] = {
    "baseline": {
        "lanes": {
            "sql": {
                "max_attempts_per_run": 2,
                "max_attempts_per_window": 2,
                "window_minutes": 5,
                "max_attempts_per_day": 6,
            },
            "web": {
                "max_attempts_per_run": 2,
                "max_attempts_per_window": 2,
                "window_minutes": 5,
                "max_attempts_per_day": 6,
            },
            "market": {
                "max_attempts_per_run": 2,
                "max_attempts_per_window": 2,
                "window_minutes": 10,
                "max_attempts_per_day": 6,
            },
            "analysis": {
                "max_attempts_per_run": 1,
                "max_attempts_per_window": 1,
                "window_minutes": 5,
                "max_attempts_per_day": 4,
            },
        }
    }
}


@dataclass(frozen=True)
class LanePolicy:
    lane: str
    max_attempts_per_run: int
    max_attempts_per_window: Optional[int]
    window_minutes: Optional[int]
    max_attempts_per_day: Optional[int]
    daily_budget: Optional[float] = None
    blocked_tags: Set[str] = field(default_factory=set)
    blocked_regions: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class DelegationContext:
    lane: str
    cost: Optional[float] = None
    spent_today: Optional[float] = None
    region: Optional[str] = None
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DelegationDecision:
    allowed: bool
    reason: str
    metadata: Dict[str, Any]


@dataclass
class DelegationPolicy:
    version: str
    lanes: Dict[str, LanePolicy]

    @classmethod
    def load(
        cls,
        *,
        version: Optional[str] = None,
        config: Optional[Mapping[str, Any]] = None,
    ) -> "DelegationPolicy":
        source_config = dict(config or {})
        policies = source_config.get("delegation_policies") or source_config
        if not isinstance(policies, Mapping):
            policies = {}
        target_version = version or "baseline"
        raw_policy = policies.get(target_version)
        if not isinstance(raw_policy, Mapping):
            raw_policy = policies.get("baseline")
        if not isinstance(raw_policy, Mapping):
            raw_policy = DEFAULT_DELEGATION_POLICIES["baseline"]

        lane_entries = raw_policy.get("lanes", {})
        lanes: Dict[str, LanePolicy] = {}
        for lane, raw_entry in lane_entries.items():
            if not isinstance(raw_entry, Mapping):
                continue
            lane_name = str(lane).strip().lower()
            if not lane_name:
                continue
            max_per_run = int(raw_entry.get("max_attempts_per_run", 2))
            max_per_window = raw_entry.get("max_attempts_per_window")
            if max_per_window is None:
                max_per_window = max_per_run
            budget_info = raw_entry.get("budget")
            daily_budget: Optional[float] = None
            if isinstance(budget_info, Mapping):
                budget_daily = budget_info.get("daily") or budget_info.get("daily_limit")
                if budget_daily is not None:
                    try:
                        daily_budget = float(budget_daily)
                    except (TypeError, ValueError):
                        daily_budget = None
            blocked_tags = cls._normalize_iterable(raw_entry.get("blocked_tags"))
            blocked_regions = cls._normalize_iterable(raw_entry.get("blocked_regions"))
            lane_policy = LanePolicy(
                lane=lane_name,
                max_attempts_per_run=max_per_run,
                max_attempts_per_window=int(max_per_window) if max_per_window is not None else None,
                window_minutes=int(raw_entry.get("window_minutes", 5)) if raw_entry.get("window_minutes") is not None else None,
                max_attempts_per_day=int(raw_entry.get("max_attempts_per_day")) if raw_entry.get("max_attempts_per_day") is not None else None,
                daily_budget=daily_budget,
                blocked_tags=blocked_tags,
                blocked_regions=blocked_regions,
            )
            lanes[lane_name] = lane_policy

        resolved_version = target_version if target_version in policies else "baseline"
        return cls(version=resolved_version, lanes=lanes)

    @staticmethod
    def _normalize_iterable(values: Optional[Iterable[Any]]) -> Set[str]:
        normalized: Set[str] = set()
        if not values:
            return normalized
        for value in values:
            if value is None:
                continue
            text = str(value).strip().lower()
            if text:
                normalized.add(text)
        return normalized

    def lane_policy(self, lane: str) -> Optional[LanePolicy]:
        return self.lanes.get(lane)

    def should_delegate(self, context: DelegationContext) -> DelegationDecision:
        lane_policy = self.lane_policy(context.lane)
        metadata: Dict[str, Any] = dict(context.metadata)
        metadata.setdefault("lane", context.lane)

        if not lane_policy:
            return DelegationDecision(allowed=True, reason="allow", metadata=metadata)

        if lane_policy.daily_budget is not None:
            spent = float(context.spent_today or 0.0)
            projected_cost = spent + float(context.cost or 0.0)
            budget_meta = {
                "daily": lane_policy.daily_budget,
                "spent": spent,
                "projected": projected_cost,
            }
            metadata["budget"] = budget_meta
            if projected_cost > lane_policy.daily_budget:
                budget_meta["overage"] = projected_cost - lane_policy.daily_budget
                return DelegationDecision(
                    allowed=False,
                    reason="quota_exceeded",
                    metadata=metadata,
                )

        if lane_policy.blocked_regions and context.region:
            region = context.region.strip().lower()
            if region in lane_policy.blocked_regions:
                metadata["region"] = region
                return DelegationDecision(
                    allowed=False,
                    reason="region_blocked",
                    metadata=metadata,
                )

        if lane_policy.blocked_tags and context.tags:
            tags_normalized = {tag.strip().lower() for tag in context.tags if isinstance(tag, str)}
            blocked = sorted(lane_policy.blocked_tags.intersection(tags_normalized))
            if blocked:
                metadata["tags_blocked"] = blocked
                return DelegationDecision(
                    allowed=False,
                    reason="tag_blocked",
                    metadata=metadata,
                )

        return DelegationDecision(allowed=True, reason="allow", metadata=metadata)

    def audit_payload(self, lane: str, decision: DelegationDecision) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "lane": lane,
            "decision": "allow" if decision.allowed else "declined",
            "policy_version": self.version,
            "policy": self.version,
            "reason": decision.reason,
        }
        if decision.metadata:
            payload["metadata"] = dict(decision.metadata)
        return payload
