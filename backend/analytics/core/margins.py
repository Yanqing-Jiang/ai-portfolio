from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional, Sequence, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .state import IntentModel, QueryPlanModel


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(str(value).lower().replace("_", " ").split())


@dataclass(frozen=True)
class MarginChoice:
    label: str
    slug: str
    synonyms: Tuple[str, ...]
    value_column: str
    value_alias: str
    peer_column: str
    peer_alias: str
    growth_column: str
    growth_alias: str
    growth_peer_column: str
    growth_peer_alias: str

    def matches(self, value: Optional[str]) -> bool:
        normalized = _normalize_text(value)
        if not normalized:
            return False
        if normalized == _normalize_text(self.label):
            return True
        if normalized == _normalize_text(self.slug):
            return True
        return any(normalized == _normalize_text(option) for option in self.synonyms)

    def appears_in_text(self, text: Optional[str]) -> bool:
        if not text:
            return False
        lowered = text.lower()
        if self.label.lower() in lowered:
            return True
        for token in self.synonyms:
            if token.lower() in lowered:
                return True
        return False


MARGIN_CHOICES: Tuple[MarginChoice, ...] = (
    MarginChoice(
        label="Gross Margin",
        slug="gross_margin",
        synonyms=("gross margin", "gross profit margin", "gm"),
        value_column="gross_margin",
        value_alias="company_gross_margin",
        peer_column="peer_avg_gross_margin",
        peer_alias="peer_avg_gross_margin",
        growth_column="gross_margin_change_pp",
        growth_alias="company_gross_margin_change_pp",
        growth_peer_column="peer_avg_gross_margin_change_pp",
        growth_peer_alias="peer_avg_gross_margin_change_pp",
    ),
    MarginChoice(
        label="Operating Margin",
        slug="operating_margin",
        synonyms=("operating margin", "operating profit margin", "op margin"),
        value_column="operating_margin",
        value_alias="company_operating_margin",
        peer_column="peer_avg_operating_margin",
        peer_alias="peer_avg_operating_margin",
        growth_column="operating_margin_change_pp",
        growth_alias="company_operating_margin_change_pp",
        growth_peer_column="peer_avg_operating_margin_change_pp",
        growth_peer_alias="peer_avg_operating_margin_change_pp",
    ),
    MarginChoice(
        label="Net Margin",
        slug="net_margin",
        synonyms=("net margin", "net profit margin", "profit margin"),
        value_column="net_margin",
        value_alias="company_net_margin",
        peer_column="peer_avg_net_margin",
        peer_alias="peer_avg_net_margin",
        growth_column="net_margin_change_pp",
        growth_alias="company_net_margin_change_pp",
        growth_peer_column="peer_avg_net_margin_change_pp",
        growth_peer_alias="peer_avg_net_margin_change_pp",
    ),
)

DEFAULT_MARGIN_LABEL = "Operating Margin"

_LOOKUP: dict[str, MarginChoice] = {}
for choice in MARGIN_CHOICES:
    keys: List[str] = [choice.label, choice.slug]
    keys.extend(choice.synonyms)
    for key in keys:
        normalized = _normalize_text(key)
        if normalized:
            _LOOKUP[normalized] = choice


def list_margin_labels() -> List[str]:
    return [choice.label for choice in MARGIN_CHOICES]


def normalize_margin_value(value: Optional[str]) -> Optional[MarginChoice]:
    normalized = _normalize_text(value)
    if not normalized:
        return None
    return _LOOKUP.get(normalized)


def detect_margin_choice_from_metrics(metrics: Iterable[str]) -> Optional[MarginChoice]:
    for metric in metrics or []:
        choice = normalize_margin_value(metric)
        if choice:
            return choice
    return None


def detect_margin_choice_from_slots(slots: Optional[Mapping[str, object]]) -> Optional[MarginChoice]:
    if not isinstance(slots, Mapping):
        return None
    explicit = slots.get("margin_choice")
    choice = normalize_margin_value(str(explicit)) if explicit is not None else None
    if choice:
        return choice
    metric_single = slots.get("metric")
    choice = normalize_margin_value(str(metric_single)) if metric_single else None
    if choice:
        return choice
    metrics_multi = slots.get("metrics")
    if isinstance(metrics_multi, (list, tuple, set)):
        choice = detect_margin_choice_from_metrics(metrics_multi)
        if choice:
            return choice
    return None


def detect_margin_choice_from_plan(plan: Optional["QueryPlanModel"]) -> Optional[MarginChoice]:
    if plan is None:
        return None
    metrics = getattr(plan, "metrics", None)
    choice = detect_margin_choice_from_metrics(metrics or [])
    if choice:
        return choice
    derived = getattr(plan, "derived_metrics", None)
    if isinstance(derived, Iterable):
        matches = [normalize_margin_value(value) for value in derived]
        unique = {match for match in matches if match is not None}
        if len(unique) == 1:
            return next(iter(unique))
    return None


def infer_margin_from_query(query: Optional[str]) -> Optional[MarginChoice]:
    for choice in MARGIN_CHOICES:
        if choice.appears_in_text(query):
            return choice
    return None


def apply_margin_choice(
    plan: Optional["QueryPlanModel"],
    intent: Optional["IntentModel"],
    choice: MarginChoice,
) -> None:
    if plan is not None:
        plan.metrics = [choice.label]
        plan.derived_metrics = [choice.slug]
    if intent is not None and isinstance(getattr(intent, "slots_detected", None), dict):
        intent.slots_detected["metric"] = choice.label
        intent.slots_detected["metrics"] = [choice.label]
        intent.slots_detected["margin_choice"] = choice.slug


def ensure_margin_choice(
    plan: Optional["QueryPlanModel"],
    intent: Optional["IntentModel"],
    slots: Optional[Mapping[str, object]],
) -> Optional[MarginChoice]:
    choice = detect_margin_choice_from_plan(plan)
    if not choice:
        choice = detect_margin_choice_from_slots(slots)
    if not choice and intent is not None:
        query_text = None
        slots_detected = getattr(intent, "slots_detected", None)
        if isinstance(slots_detected, Mapping):
            query_text = slots_detected.get("original_query")
        if query_text is None and hasattr(intent, "assumptions"):
            query_text = next(
                (assumption for assumption in intent.assumptions if isinstance(assumption, str) and "margin" in assumption.lower()),
                None,
            )
        choice = infer_margin_from_query(query_text)
        if choice:
            apply_margin_choice(plan, intent, choice)
    elif choice:
        apply_margin_choice(plan, intent, choice)
    return choice
