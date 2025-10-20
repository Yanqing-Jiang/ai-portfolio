"""
Intent Normalization Functions

Shared functions for normalizing and processing intent-related data across
analytics_memory and analytics_supervisor systems.
"""

import math
import re
from datetime import datetime
from typing import Any, Dict, List, Optional


NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _get_timeframe_preset_map(configs: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Build a lookup table for timeframe presets using slot suggestions.
    Keys include both labels and canonical values (plus aliases).
    """
    metrics_cfg = configs.get("metrics") if isinstance(configs, dict) else {}
    slot_suggestions = metrics_cfg.get("slot_suggestions", {}) if isinstance(metrics_cfg, dict) else {}
    preset_entries = slot_suggestions.get("timeframe_presets") if isinstance(slot_suggestions, dict) else None

    mapping: Dict[str, Dict[str, Any]] = {}
    if isinstance(preset_entries, list):
        for entry in preset_entries:
            if isinstance(entry, str):
                label = entry.strip()
                if not label:
                    continue
                record = {"label": label}
                mapping[label.lower()] = record
                continue

            if not isinstance(entry, dict):
                continue

            label = str(entry.get("label") or entry.get("value") or "").strip()
            value = str(entry.get("value") or entry.get("label") or "").strip()
            record: Dict[str, Any] = {
                "label": label,
                "value": value,
            }
            for key in ("years_back", "quarters_back", "year_to_date", "start_year", "end_year", "granularity"):
                if key in entry:
                    record[key] = entry[key]

            keys: List[str] = []
            if label:
                keys.append(label.lower())
            if value:
                keys.append(value.lower())
            aliases = entry.get("aliases")
            if isinstance(aliases, list):
                for alias in aliases:
                    if isinstance(alias, str) and alias.strip():
                        keys.append(alias.strip().lower())

            for key in keys:
                mapping[key] = record

    return mapping


def _apply_preset(record: Dict[str, Any], timeframe: Dict[str, Any]) -> None:
    """Populate timeframe settings based on preset metadata."""
    if not record:
        return

    if record.get("value"):
        timeframe["preset"] = record["value"]
    elif record.get("label"):
        timeframe["preset"] = record["label"]

    if "years_back" in record and isinstance(record["years_back"], (int, float)):
        timeframe["years_back"] = int(record["years_back"])

    if "quarters_back" in record and isinstance(record["quarters_back"], (int, float)):
        quarters = int(record["quarters_back"])
        timeframe["quarters_back"] = quarters
        timeframe.setdefault("years_back", max(1, math.ceil(quarters / 4)))

    if record.get("year_to_date"):
        year = datetime.utcnow().year
        timeframe["start_year"] = year
        timeframe["end_year"] = year
        timeframe["year_to_date"] = True

    if "start_year" in record and isinstance(record["start_year"], int):
        timeframe["start_year"] = record["start_year"]
    if "end_year" in record and isinstance(record["end_year"], int):
        timeframe["end_year"] = record["end_year"]
    if "granularity" not in timeframe:
        label_hint = str(record.get("label") or record.get("value") or "").lower()
        if record.get("year_to_date"):
            timeframe["granularity"] = "quarterly"
        elif "quarter" in label_hint:
            timeframe["granularity"] = "quarterly"
        elif "year" in label_hint and "quarter" not in label_hint:
            timeframe["granularity"] = "annual"


def normalize_timeframe(
    tf_raw: Any,
    query_text: str = "",
    configs: Dict = None,
    *,
    apply_defaults: bool = True,
    origin: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Normalize timeframe from various formats to a consistent dict structure.

    Args:
        tf_raw: Raw timeframe from LLM (could be dict, string, or None)
        query_text: Original query text for fallback parsing
        configs: Configuration dict for defaults
        apply_defaults: Whether to fall back to configuration defaults when no value detected
        origin: Optional hint describing the source of the timeframe ("query", "clarification", etc.)

    Returns:
        Dict with normalized timeframe structure
    """
    text = (query_text or "").lower()
    configs = configs or {}
    preset_map = _get_timeframe_preset_map(configs)

    detected = False
    source = origin.lower() if isinstance(origin, str) and origin else None

    def mark_detected(default_source: Optional[str] = None) -> None:
        nonlocal detected, source
        detected = True
        if default_source and not source:
            source = default_source

    tf: Dict[str, Any] = {}

    # Normalise Pydantic models to dicts without circular imports
    if hasattr(tf_raw, "model_dump"):
        try:
            tf_raw = tf_raw.model_dump(exclude_none=True)
        except TypeError:
            tf_raw = tf_raw.model_dump()
    elif hasattr(tf_raw, "dict"):
        tf_raw = tf_raw.dict()

    if isinstance(tf_raw, dict):
        for key, value in tf_raw.items():
            if key == "source":
                if isinstance(value, str) and value.strip():
                    source = source or value.strip().lower()
                continue
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            tf[key] = value
        preset_key = None
        if "preset" in tf and isinstance(tf["preset"], str):
            preset_key = tf["preset"].strip().lower()
        elif "value" in tf and isinstance(tf["value"], str):
            preset_key = tf["value"].strip().lower()
        if preset_key:
            preset_record = preset_map.get(preset_key)
            has_bounds = any(
                key in tf for key in ("years_back", "quarters_back", "start_year", "end_year")
            )
            if preset_record and not has_bounds:
                _apply_preset(preset_record, tf)
        if tf:
            mark_detected(source or "clarification")
    elif isinstance(tf_raw, str):
        tf_str = tf_raw.strip()
        lowered = tf_str.lower()

        preset_record = preset_map.get(lowered)
        if preset_record:
            _apply_preset(preset_record, tf)
            mark_detected(source or "query")
        else:
            years_match = re.search(r"(\d{1,2})\s*years?", lowered)
            quarters_match = re.search(r"(\d{1,2})\s*quarters?", lowered)

            if years_match:
                tf["years_back"] = int(years_match.group(1))
                mark_detected(source or "query")
            elif quarters_match:
                quarters = int(quarters_match.group(1))
                tf["quarters_back"] = quarters
                tf["years_back"] = max(1, math.ceil(quarters / 4))
                mark_detected(source or "query")

            words_match = re.search(
                r"(past|last)\s+(one|two|three|four|five|six|seven|eight|nine|ten)\s+years?",
                lowered,
            )
            if words_match and "years_back" not in tf:
                word = words_match.group(2)
                value = NUMBER_WORDS.get(word, 0)
                if value:
                    tf["years_back"] = value
                    mark_detected(source or "query")

            quarters_word_match = re.search(
                r"(past|last)\s+(one|two|three|four|five|six|seven|eight|nine|ten)\s+quarters?",
                lowered,
            )
            if quarters_word_match and "quarters_back" not in tf:
                word = quarters_word_match.group(2)
                quarters = NUMBER_WORDS.get(word, 0)
                if quarters:
                    tf["quarters_back"] = quarters
                    tf.setdefault("years_back", max(1, math.ceil(quarters / 4)))
                    mark_detected(source or "query")

            range_match = re.search(r"(19|20)\d{2}\s*(?:-|to|through)\s*(19|20)\d{2}", lowered)
            if range_match:
                parts = re.findall(r"(19|20)\d{2}", lowered)
                if len(parts) >= 2:
                    start_year = int(parts[0])
                    end_year = int(parts[1])
                    if start_year <= end_year:
                        tf["start_year"] = start_year
                        tf["end_year"] = end_year
                        tf.setdefault("years_back", max(1, end_year - start_year + 1))
                        mark_detected(source or "query")

            single_year_match = re.search(r"(19|20)\d{2}", lowered)
            if single_year_match and "start_year" not in tf and "end_year" not in tf:
                year = int(single_year_match.group(0))
                tf["start_year"] = year
                tf["end_year"] = year
                tf.setdefault("years_back", 1)
                mark_detected(source or "query")

            if "year_to_date" not in tf and ("year to date" in lowered or "ytd" in lowered.replace("-", "")):
                _apply_preset(
                    preset_map.get("year to date") or {"value": "year_to_date", "year_to_date": True},
                    tf,
                )
                mark_detected(source or "query")

    # Fallback: parse from original query text
    years_m = re.search(r"(past|last)\s+(\d{1,2})\s+years?", text)
    quarters_m = re.search(r"(past|last)\s+(\d{1,2})\s+quarters?", text)

    if not tf.get("years_back"):
        words_years = re.search(r"(past|last)\s+(one|two|three|four|five|six|seven|eight|nine|ten)\s+years?", text)
        if words_years:
            detected_value = NUMBER_WORDS.get(words_years.group(2))
            if detected_value:
                tf["years_back"] = detected_value
                mark_detected(source or "query")

    if years_m and not tf.get("years_back"):
        tf["years_back"] = int(years_m.group(2))
        mark_detected(source or "query")
    if quarters_m and not tf.get("quarters_back"):
        tf["quarters_back"] = int(quarters_m.group(2))
        tf.setdefault("years_back", max(1, math.ceil(tf["quarters_back"] / 4)))
        mark_detected(source or "query")

    if not apply_defaults and not detected:
        return {}

    if configs:
        dbq = (configs.get("database", {}) or {}).get("query_defaults", {})
        max_years = int(dbq.get("max_years_back", 10))
        default_years = int(dbq.get("default_years_back", 5))

        if apply_defaults and not tf.get("years_back") and not tf.get("quarters_back"):
            tf["years_back"] = default_years
            mark_detected(source or "default")

        if tf.get("years_back"):
            tf["years_back"] = min(max(int(tf["years_back"]), 1), max_years)
        if tf.get("quarters_back"):
            tf["quarters_back"] = min(max(int(tf["quarters_back"]), 1), max_years * 4)
            tf.setdefault("years_back", max(1, math.ceil(tf["quarters_back"] / 4)))

        start_year = tf.get("start_year")
        end_year = tf.get("end_year")
        if isinstance(start_year, int) and isinstance(end_year, int) and start_year <= end_year:
            span = end_year - start_year + 1
            tf.setdefault("years_back", min(max(span, 1), max_years))

    if not tf:
        return {}

    tf.pop("value", None)
    tf.pop("label", None)

    if "granularity" not in tf:
        if tf.get("quarters_back"):
            tf["granularity"] = "quarterly"
        elif tf.get("year_to_date"):
            tf["granularity"] = "quarterly"
        elif tf.get("years_back") or tf.get("start_year") or tf.get("end_year"):
            tf["granularity"] = "annual"

    if source:
        tf["source"] = source
    elif detected:
        tf["source"] = "query"
    else:
        tf["source"] = "default"

    return tf


def build_metric_lookup(configs: Dict[str, Any]) -> Dict[str, str]:
    """
    Build a lookup of lowercase metric aliases -> canonical metric names.
    """
    metrics_cfg = configs.get("metrics") if isinstance(configs, dict) else {}
    lookup: Dict[str, str] = {}

    if isinstance(metrics_cfg, dict):
        base_metrics = metrics_cfg.get("metrics")
        if isinstance(base_metrics, dict):
            for entry in base_metrics.values():
                if not isinstance(entry, dict):
                    continue
                canonical = str(entry.get("name") or "").strip()
                metric_id = str(entry.get("metric_id") or "").strip()
                database_name = str(entry.get("database_name") or "").strip()
                candidates = [canonical, metric_id, database_name]
                aliases = entry.get("aliases")
                if isinstance(aliases, list):
                    candidates.extend(
                        str(alias) for alias in aliases if isinstance(alias, (str, bytes))
                    )
                for candidate in candidates:
                    value = str(candidate or "").strip()
                    if not value:
                        continue
                    lookup[value.lower()] = canonical or value

        synonyms = metrics_cfg.get("synonyms")
        if isinstance(synonyms, dict):
            for alias, target in synonyms.items():
                alias_key = str(alias or "").strip().lower()
                if not alias_key:
                    continue
                if isinstance(target, str):
                    canonical_lookup = lookup.get(target.lower(), target)
                    lookup[alias_key] = canonical_lookup
                elif isinstance(target, list) and target:
                    primary = str(target[0]).strip()
                    if primary:
                        lookup[alias_key] = lookup.get(primary.lower(), primary)

    return lookup


def normalize_metrics(raw: Any, configs: Dict[str, Any]) -> List[str]:
    """
    Normalize metric identifiers (single value or list) to canonical names.
    """
    if raw is None:
        return []

    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, (list, tuple, set)):
        values = list(raw)
    else:
        return []

    lookup = build_metric_lookup(configs)
    normalized: List[str] = []
    seen: set[str] = set()

    for entry in values:
        if not isinstance(entry, str):
            continue
        candidate = entry.strip()
        if not candidate:
            continue
        canonical = lookup.get(candidate.lower(), candidate)
        lowered = canonical.lower()
        if lowered in seen:
            continue
        normalized.append(canonical)
        seen.add(lowered)

    return normalized


def get_default_tickers(configs: Dict[str, Any]) -> List[str]:
    """
    Get default ticker list from configuration.

    Args:
        configs: Configuration dictionary

    Returns:
        List of default ticker symbols
    """
    return (
        configs.get("companies", {})
        .get("selection_rules", {})
        .get("default_companies", {})
        .get("tickers", ["NVDA", "AMD", "INTC", "MU", "QCOM", "AVGO", "TXN"])
    )


def timeframe_implies_quarterly(timeframe: Any) -> bool:
    """
    Determine whether a provided timeframe should force quarterly granularity.

    Args:
        timeframe: A TimeframeModel, dict, or other mapping-like object.

    Returns:
        True if quarterly granularity should be enforced, False otherwise.
    """
    if timeframe is None:
        return False

    tf_dict: Dict[str, Any]
    if hasattr(timeframe, "model_dump"):
        try:
            tf_dict = timeframe.model_dump()
        except Exception:  # pragma: no cover - defensive catch
            tf_dict = dict(getattr(timeframe, "__dict__", {}))
    elif isinstance(timeframe, dict):
        tf_dict = timeframe
    else:
        return False

    if not isinstance(tf_dict, dict):
        return False

    def _string_fields_contain(keyword: str) -> bool:
        lowered = keyword.lower()
        for key in ("preset", "label", "value", "display", "raw", "original", "granularity"):
            value = tf_dict.get(key)
            if isinstance(value, str) and lowered in value.lower():
                return True
        return False

    if _string_fields_contain("quarter"):
        return True

    if tf_dict.get("year_to_date") is True:
        return True

    quarters_back = tf_dict.get("quarters_back")
    if isinstance(quarters_back, (int, float)) and quarters_back > 0:
        return True

    granularity = tf_dict.get("granularity")
    if isinstance(granularity, str) and "quarter" in granularity.lower():
        return True

    years_back = tf_dict.get("years_back")
    source = str(tf_dict.get("source") or "").lower()
    if isinstance(years_back, (int, float)):
        years_int = int(years_back)
        if years_int == 2:
            if source in {"query", "clarification"} or not source:
                return True
            if (
                _string_fields_contain("2 year")
                or _string_fields_contain("two year")
                or _string_fields_contain("2_year")
                or _string_fields_contain("last_2_year")
            ):
                return True

    return False


def normalize_granularity(query: str, current_granularity: Optional[str] = None) -> str:
    """
    Normalize granularity from query or use provided value.

    Args:
        query: Original query text
        current_granularity: Current granularity value from slots

    Returns:
        Normalized granularity ("annual" or "quarterly")
    """
    query_lower = (query or "").lower()

    if current_granularity and current_granularity in ["annual", "quarterly"]:
        if current_granularity == "annual":
            if any(k in query_lower for k in ["quarter", "qoq", "q1", "q2", "q3", "q4"]):
                return "quarterly"
        return current_granularity

    if any(k in query_lower for k in ["quarter", "qoq", "q1", "q2", "q3", "q4"]):
        return "quarterly"
    else:
        return "annual"
