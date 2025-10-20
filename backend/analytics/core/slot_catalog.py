"""
Slot catalog utilities for unified intent clarification.

Builds lightweight hints from YAML configs that can be passed to the intent
resolver and frontend clarification UI. The catalog is advisory only and does
not enforce deterministic validation – the LLM remains responsible for marking
slots as filled, missing, or defaulted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .config import CONFIGS, Configs


@dataclass(frozen=True)
class SlotOption:
    """Suggested values and presets for a particular slot."""

    suggestions: List[str] = field(default_factory=list)
    presets: List[str] = field(default_factory=list)
    allow_custom: bool = True
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "suggestions": list(self.suggestions),
            "presets": list(self.presets),
            "allow_custom": self.allow_custom,
            "description": self.description,
        }


@dataclass(frozen=True)
class IntentSlotDefinition:
    """Slot requirements and advisory options for a specific intent."""

    intent_key: str
    required_slots: List[str] = field(default_factory=list)
    optional_slots: List[str] = field(default_factory=list)
    slot_options: Dict[str, SlotOption] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "intent_key": self.intent_key,
            "required_slots": list(self.required_slots),
            "optional_slots": list(self.optional_slots),
            "slot_options": {slot: option.to_dict() for slot, option in self.slot_options.items()},
        }


def _normalize_slot_name(raw_slot: str) -> str:
    """Collapse dotted slots such as timeframe.start_year -> timeframe."""
    if not raw_slot:
        return raw_slot
    return raw_slot.split(".", 1)[0]


def _collect_company_suggestions(configs: Configs) -> List[str]:
    companies_cfg = (configs.companies or {}).get("companies", {})
    ranked: List[tuple[int, str]] = []

    for sector_companies in companies_cfg.values():
        if not isinstance(sector_companies, list):
            continue
        for entry in sector_companies:
            if not isinstance(entry, dict):
                continue
            ticker = entry.get("ticker")
            if not ticker:
                continue
            priority = entry.get("priority")
            if isinstance(priority, int):
                ranked.append((priority, ticker))
            else:
                ranked.append((999, ticker))

    ranked.sort(key=lambda pair: (pair[0], pair[1]))
    suggestions = [ticker for _, ticker in ranked]

    # Ensure we always expose a catch-all option.
    if "ALL" not in suggestions:
        suggestions.append("ALL")

    return suggestions


def _collect_metric_suggestions(configs: Configs, limit: int = 16) -> List[str]:
    metrics_cfg = configs.metrics or {}
    slot_suggestions = metrics_cfg.get("slot_suggestions", {}) if isinstance(metrics_cfg, dict) else {}

    curated: List[str] = []
    if isinstance(slot_suggestions, dict):
        raw_metrics = slot_suggestions.get("metric")
        if isinstance(raw_metrics, list):
            seen = set()
            for entry in raw_metrics:
                if not isinstance(entry, str):
                    continue
                normalized = entry.strip()
                if not normalized:
                    continue
                lowered = normalized.lower()
                if lowered in seen:
                    continue
                curated.append(normalized)
                seen.add(lowered)
                if limit and len(curated) >= limit:
                    return curated
    if curated:
        return curated

    metrics_section = metrics_cfg.get("metrics", {}) if isinstance(metrics_cfg, dict) else {}
    collected: List[str] = []

    for key, entry in metrics_section.items():
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") or key
        if isinstance(name, str):
            collected.append(name)
        aliases = entry.get("aliases")
        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str):
                    collected.append(alias)

    seen = set()
    deduped: List[str] = []
    for value in collected:
        normalized = value.strip()
        if not normalized or normalized.lower() in seen:
            continue
        deduped.append(normalized)
        seen.add(normalized.lower())
        if limit and len(deduped) >= limit:
            break

    return deduped


def _collect_timeframe_presets(configs: Configs) -> List[str]:
    metrics_cfg = configs.metrics or {}
    slot_suggestions = metrics_cfg.get("slot_suggestions", {}) if isinstance(metrics_cfg, dict) else {}

    labels: List[str] = []
    if isinstance(slot_suggestions, dict):
        preset_entries = slot_suggestions.get("timeframe_presets")
        if isinstance(preset_entries, list):
            seen = set()
            for entry in preset_entries:
                if isinstance(entry, str):
                    label = entry.strip()
                elif isinstance(entry, dict):
                    label = str(entry.get("label") or entry.get("value") or "").strip()
                else:
                    label = ""
                if not label:
                    continue
                lowered = label.lower()
                if lowered in seen:
                    continue
                labels.append(label)
                seen.add(lowered)
    if labels:
        return labels

    query_defaults = metrics_cfg.get("query_defaults", {}) if isinstance(metrics_cfg, dict) else {}
    fallback_defaults = ["last 5 years", "last 2 years", "last 8 quarters", "year to date"]
    seen = set()
    presets: List[str] = []

    for preset in fallback_defaults:
        lowered = preset.lower()
        if lowered in seen:
            continue
        presets.append(preset)
        seen.add(lowered)

    custom_presets = query_defaults.get("preset_timeframes")
    if isinstance(custom_presets, list):
        for preset in custom_presets:
            if not isinstance(preset, str):
                continue
            label = preset.strip()
            if not label:
                continue
            lowered = label.lower()
            if lowered in seen:
                continue
            presets.append(label)
            seen.add(lowered)

    return presets


def _build_global_slot_options(configs: Configs) -> Dict[str, SlotOption]:
    return {
        "company": SlotOption(
            suggestions=_collect_company_suggestions(configs),
            allow_custom=True,
            description="Company tickers available for analysis.",
        ),
        "metric": SlotOption(
            suggestions=_collect_metric_suggestions(configs),
            allow_custom=True,
            description="Financial metrics that can be analysed or visualised.",
        ),
        "timeframe": SlotOption(
            suggestions=_collect_timeframe_presets(configs),
            presets=_collect_timeframe_presets(configs),
            allow_custom=True,
            description="Common timeframe presets (custom inputs allowed).",
        ),
        "granularity": SlotOption(
            suggestions=["annual", "quarterly"],
            allow_custom=False,
            description="Reporting cadence for the requested analysis.",
        ),
        "comparison": SlotOption(
            suggestions=["single", "all"],
            allow_custom=False,
            description="Whether to analyse a single company or compare across the catalog.",
        ),
    }


DEFAULT_OPTIONAL_SLOTS: Iterable[str] = ("timeframe", "metric", "granularity", "comparison")


class SlotCatalog:
    """Materialised view of intent slots derived from YAML configs."""

    def __init__(self, configs: Configs) -> None:
        self._configs = configs
        self._global_options = _build_global_slot_options(configs)
        self._intent_map: Dict[str, IntentSlotDefinition] = {}
        self._build_intent_map()

    def _build_intent_map(self) -> None:
        required_slots_cfg = (self._configs.query_requirements or {}).get("required_slots", {})
        if not isinstance(required_slots_cfg, dict):
            required_slots_cfg = {}

        for intent_key, slots in required_slots_cfg.items():
            normalized_required: List[str] = []
            if isinstance(slots, list):
                for slot in slots:
                    if not isinstance(slot, str):
                        continue
                    normalized = _normalize_slot_name(slot)
                    if normalized and normalized not in normalized_required:
                        normalized_required.append(normalized)

            slot_options: Dict[str, SlotOption] = {}
            for slot_key, option in self._global_options.items():
                if slot_key in normalized_required or slot_key in DEFAULT_OPTIONAL_SLOTS:
                    slot_options[slot_key] = SlotOption(
                        suggestions=list(option.suggestions),
                        presets=list(option.presets),
                        allow_custom=option.allow_custom,
                        description=option.description,
                    )

            optional_slots = [slot for slot in DEFAULT_OPTIONAL_SLOTS if slot not in normalized_required]

            self._intent_map[intent_key] = IntentSlotDefinition(
                intent_key=intent_key,
                required_slots=normalized_required,
                optional_slots=optional_slots,
                slot_options=slot_options,
            )

        # Ensure all intents defined in queries.yaml have an entry, even if they
        # do not list required slots yet.
        query_patterns = (self._configs.queries or {}).get("query_patterns", {})
        if isinstance(query_patterns, dict):
            for intent_key in query_patterns.keys():
                if intent_key in self._intent_map:
                    continue
                slot_options = {
                    slot_key: SlotOption(
                        suggestions=list(option.suggestions),
                        presets=list(option.presets),
                        allow_custom=option.allow_custom,
                        description=option.description,
                    )
                    for slot_key, option in self._global_options.items()
                }
                optional_slots = [slot for slot in DEFAULT_OPTIONAL_SLOTS]
                self._intent_map[intent_key] = IntentSlotDefinition(
                    intent_key=intent_key,
                    required_slots=[],
                    optional_slots=optional_slots,
                    slot_options=slot_options,
                )

    def list_intents(self) -> List[str]:
        return sorted(self._intent_map.keys())

    def get_intent_definition(self, intent_key: str) -> Optional[IntentSlotDefinition]:
        return self._intent_map.get(intent_key)

    def get_slot_options(self, slot_key: str) -> Optional[SlotOption]:
        option = self._global_options.get(slot_key)
        if not option:
            return None
        return SlotOption(
            suggestions=list(option.suggestions),
            presets=list(option.presets),
            allow_custom=option.allow_custom,
            description=option.description,
        )


_SLOT_CATALOG: Optional[SlotCatalog] = None


def get_slot_catalog(*, refresh: bool = False) -> SlotCatalog:
    """
    Return a memoised SlotCatalog built from CONFIGS.

    Passing refresh=True rebuilds the catalog – useful in tests that mutate the
    underlying configuration.
    """
    global _SLOT_CATALOG
    if refresh or _SLOT_CATALOG is None:
        _SLOT_CATALOG = SlotCatalog(CONFIGS)
    return _SLOT_CATALOG
