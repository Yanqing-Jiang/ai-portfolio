"""Snapshot v2 data_model: A2UI accumulator + legacy-column normalizer.

Mirrors useFortuneStream.processContents, fortuneStore.applyPatch, buildReplayDataModel.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Iterable, Mapping, MutableMapping

_ELEMENT_BY_LOWER = {
    "wood": "Wood", "fire": "Fire", "earth": "Earth",
    "metal": "Metal", "water": "Water",
}
_ELEMENT_VALUE_KEYS = {
    "element", "dayMasterElement", "day_master_element",
    "stemElement", "stem_element", "branchElement", "branch_element",
}

def _normalize_element_name(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return _ELEMENT_BY_LOWER.get(value.strip().lower(), value)

def _normalize_stream_value(key: str, value: Any) -> Any:
    if key in _ELEMENT_VALUE_KEYS:
        return _normalize_element_name(value)
    if isinstance(value, list):
        return [_normalize_stream_value("", item) for item in value]
    if not isinstance(value, dict):
        return value
    out: dict[str, Any] = {}
    for k, v in value.items():
        nk = _ELEMENT_BY_LOWER.get(str(k).lower(), k)
        out[nk] = _normalize_stream_value(str(k), v)
    return out

def _normalize_array(arr: Any) -> list[Any]:
    if not isinstance(arr, list):
        return []
    result: list[Any] = []
    for item in arr:
        if isinstance(item, list) and item and isinstance(item[0], dict) and "key" in item[0]:
            result.append(process_contents(item))
        elif isinstance(item, dict) and "valueMap" in item:
            result.append(process_contents(item.get("valueMap")))
        elif isinstance(item, dict) and "valueObject" in item:
            result.append(process_contents(item.get("valueObject")))
        else:
            result.append(_normalize_stream_value("", item))
    return result

def process_contents(contents: Any) -> dict[str, Any]:
    """Convert A2UI DataEntry[] (or plain object) into a nested dict."""
    if not isinstance(contents, list):
        if isinstance(contents, dict):
            return _normalize_stream_value("", contents)  # type: ignore[return-value]
        return {}
    result: dict[str, Any] = {}
    for entry in contents:
        if not isinstance(entry, dict) or "key" not in entry:
            continue
        key = str(entry["key"])
        if entry.get("valueString") is not None:
            result[key] = _normalize_stream_value(key, entry["valueString"])
        elif entry.get("valueNumber") is not None:
            result[key] = entry["valueNumber"]
        elif entry.get("valueBoolean") is not None:
            result[key] = entry["valueBoolean"]
        elif entry.get("valueBool") is not None:
            result[key] = entry["valueBool"]
        elif entry.get("valueArray") is not None:
            result[key] = _normalize_stream_value(key, _normalize_array(entry["valueArray"]))
        elif entry.get("valueMap") is not None:
            result[key] = _normalize_stream_value(key, process_contents(entry["valueMap"]))
        elif entry.get("valueObject") is not None:
            obj = entry["valueObject"]
            if isinstance(obj, list):
                result[key] = _normalize_stream_value(key, process_contents(obj))
            elif isinstance(obj, dict):
                result[key] = _normalize_stream_value(key, obj)
    return result

def _strip_data_prefix(path: str | None) -> str:
    if not path:
        return ""
    clean = path
    if clean.startswith("/data/"):
        clean = clean[6:]
    elif clean.startswith("/data"):
        clean = clean[5:]
    return clean[1:] if clean.startswith("/") else clean

def apply_patch(model: MutableMapping[str, Any], path: str | None, value: Any) -> dict[str, Any]:
    """Merge ``value`` at path — mirrors fortuneStore.applyPatch."""
    if not isinstance(model, dict):
        model = {}
    clean = _strip_data_prefix(path)
    if not clean:
        if isinstance(value, dict):
            model.update(value)
        return dict(model)
    segments = clean.split("/")
    current: MutableMapping[str, Any] = model
    for seg in segments[:-1]:
        if not isinstance(current.get(seg), dict):
            current[seg] = {}
        current = current[seg]  # type: ignore[assignment]
    last = segments[-1]
    existing = current.get(last)
    if isinstance(existing, dict) and isinstance(value, dict) and not isinstance(existing, list):
        existing.update(value)
    else:
        current[last] = value
    return dict(model)

def apply_data_model_update(
    model: MutableMapping[str, Any] | None,
    path: str | None,
    contents: Any,
) -> dict[str, Any]:
    return apply_patch(dict(model or {}), path, process_contents(contents))

def apply_envelope_payload(model: MutableMapping[str, Any] | None, payload: Any) -> dict[str, Any]:
    base: dict[str, Any] = dict(model or {})
    if not isinstance(payload, dict):
        return base
    dmu = payload.get("dataModelUpdate")
    if not isinstance(dmu, dict):
        return base
    return apply_data_model_update(base, dmu.get("path"), dmu.get("contents"))

def accumulate_from_envelopes(
    envelopes: Iterable[Mapping[str, Any]],
    *,
    model: MutableMapping[str, Any] | None = None,
) -> dict[str, Any]:
    acc: dict[str, Any] = dict(model or {})
    for env in envelopes:
        if isinstance(env, Mapping):
            acc = apply_envelope_payload(acc, env.get("payload"))
    return acc

class DataModelAccumulator:
    """Mutable server-side mirror of the frontend Zustand dataModel."""

    __slots__ = ("_model",)

    def __init__(self, initial: Mapping[str, Any] | None = None) -> None:
        self._model: dict[str, Any] = dict(initial or {})

    @property
    def model(self) -> dict[str, Any]:
        return self._model

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self._model)

    def apply_payload(self, payload: Any) -> dict[str, Any]:
        self._model = apply_envelope_payload(self._model, payload)
        return self._model

    def apply_envelope(self, envelope: Mapping[str, Any] | None) -> dict[str, Any]:
        if not envelope:
            return self._model
        return self.apply_payload(envelope.get("payload"))

    def apply_sse_chunk(self, chunk: str) -> dict[str, Any]:
        for line in chunk.splitlines():
            if not line.startswith("data: "):
                continue
            try:
                env = json.loads(line[6:])
            except (TypeError, ValueError):
                continue
            if isinstance(env, dict):
                self.apply_envelope(env)
        return self._model

def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}

def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []

def _snake_to_camel_key(key: str) -> str:
    if "_" not in key:
        return key
    parts = key.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:] if p)

def _deep_camelize(value: Any) -> Any:
    if isinstance(value, list):
        return [_deep_camelize(v) for v in value]
    if not isinstance(value, dict):
        return value
    return {_snake_to_camel_key(str(k)): _deep_camelize(v) for k, v in value.items()}

def data_model_from_legacy_columns(
    *,
    overview: Any = None,
    pillars: Any = None,
    mechanics: Any = None,
    narrative: Any = None,
    trace: Any = None,
    references: Any = None,
    retrodictions: Any = None,
    focus: str | None = None,
) -> dict[str, Any]:
    """Rebuild FortuneDataModel-shaped dict from v1 ``latest_*`` columns."""
    overview_d, pillars_d = _as_dict(overview), _as_dict(pillars)
    mechanics_d, narrative_d = _as_dict(mechanics), _as_dict(narrative)
    references_d, retro_d = _as_dict(references), _as_dict(retrodictions)
    pillars_raw = pillars_d.get("pillars") or mechanics_d.get("pillars") or pillars_d
    elements_raw = pillars_d.get("elements") or mechanics_d.get("enhanced_element_counts")
    model: dict[str, Any] = {}

    if overview_d:
        apply_patch(model, "/data", _deep_camelize(overview_d))
    if pillars_raw:
        apply_patch(model, "/data/pillars", _deep_camelize(pillars_raw))
    if elements_raw:
        apply_patch(model, "/data/elements", _deep_camelize(elements_raw))
    if mechanics_d.get("hidden_stems"):
        apply_patch(model, "/data/hiddenStems", _deep_camelize(mechanics_d["hidden_stems"]))
    if mechanics_d.get("ten_gods") is not None:
        apply_patch(model, "/data/tenGods", {"items": _deep_camelize(_as_list(mechanics_d["ten_gods"]))})
    if mechanics_d.get("interactions") is not None:
        apply_patch(model, "/data/interactions", {"items": _deep_camelize(_as_list(mechanics_d["interactions"]))})
    if mechanics_d.get("seasonal_strength"):
        apply_patch(model, "/data/seasonalStrength", _deep_camelize(mechanics_d["seasonal_strength"]))
    if mechanics_d.get("element_by_source"):
        apply_patch(model, "/data/elementBySource", _deep_camelize(mechanics_d["element_by_source"]))
    if mechanics_d.get("luck_pillars") is not None:
        apply_patch(model, "/data/luckPillars", {"items": _deep_camelize(_as_list(mechanics_d["luck_pillars"]))})
    if mechanics_d.get("annual_pillars") is not None:
        apply_patch(model, "/data/annualPillars", {"items": _deep_camelize(_as_list(mechanics_d["annual_pillars"]))})

    pillars_cam = _as_dict(model.get("pillars"))
    seasonal_cam = _as_dict(model.get("seasonalStrength"))
    kpi = {
        "dayMaster": pillars_cam.get("dayMaster") or _as_dict(pillars_cam.get("day")).get("stem"),
        "dayMasterElement": _normalize_element_name(
            pillars_cam.get("dayMasterElement") or pillars_cam.get("day_master_element")
        ),
        "harmonyScore": mechanics_d.get("harmony_score"),
        "seasonalStrength": seasonal_cam.get("strength"),
        "seasonalScore": seasonal_cam.get("score"),
    }
    apply_patch(model, "/data/kpi", {k: v for k, v in kpi.items() if v is not None})

    if narrative_d:
        apply_patch(model, "/data/narrative", _deep_camelize({
            "tldr": narrative_d.get("tldr", ""),
            "insights": narrative_d.get("insights", []),
            "year_predictions": narrative_d.get("year_predictions", []),
            "isComplete": True,
        }))
        focus_s = str(focus or "")
        for src_key, path, also in (
            ("wish", "/data/wish", "wish" in focus_s),
            ("luck_cycle", "/data/luckCycle", focus_s.startswith("luck_cycle")),
            ("compatibility", "/data/compatibility", focus_s.startswith("compatibility")),
            ("occasion", "/data/occasion", focus_s.startswith("occasion")),
        ):
            block = narrative_d.get(src_key)
            if block or also:
                if block:
                    apply_patch(model, path, _deep_camelize(block))

    ref_items = references_d.get("items") if "items" in references_d else references_d
    if ref_items:
        items = ref_items if isinstance(ref_items, list) else _as_list(ref_items)
        apply_patch(model, "/data/classics", {"references": _deep_camelize(items)})
    if trace:
        apply_patch(model, "/data/trace", _deep_camelize(trace))
    if retro_d:
        if retro_d.get("items") is not None:
            apply_patch(model, "/data/retrodictions", {"items": _deep_camelize(_as_list(retro_d["items"]))})
        if retro_d.get("corrections"):
            apply_patch(model, "/data/corrections", _deep_camelize(retro_d["corrections"]))
    return model
