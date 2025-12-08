# --- Analytics Function/Class Map ---
# Functions: normalize_chart_patch, apply_chart_patch_to_spec
#   Role: Normalize chart patch payloads and apply patch ops to ECharts options.
#   Called from: analytics.core.charting.revision_emitters, analytics.core.charting.revision_classifiers
#   Invokes: Internal helpers (_ensure_legend, _axis_as_list)
#   Why: Centralizes chart patch logic for reuse across flows and tests.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional


def normalize_chart_patch(
    patch: Dict[str, Any],
    *,
    reason: Optional[str] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """Ensure downstream consumers receive a consistent chart patch payload."""
    if not isinstance(patch, dict):
        raise ValueError("chart patch payload must be a dictionary")
    ops = patch.get("ops")
    if not isinstance(ops, list) or not all(isinstance(op, dict) for op in ops):
        raise ValueError("chart patch requires a list of operation dictionaries")
    normalized: Dict[str, Any] = {"ops": [dict(op) for op in ops]}
    normalized_reason = reason or patch.get("reason")
    if normalized_reason:
        normalized["reason"] = normalized_reason
    normalized_source = source or patch.get("source")
    if normalized_source:
        normalized["source"] = normalized_source
    chart_id = patch.get("chart_id")
    if isinstance(chart_id, str) and chart_id:
        normalized["chart_id"] = chart_id
    return normalized


def _ensure_legend(option: Dict[str, Any]) -> Dict[str, Any]:
    legend = option.get("legend")
    if isinstance(legend, list):
        legend_obj = legend[0] if legend else {}
        option["legend"] = legend_obj or {}
    elif legend is None or not isinstance(legend, dict):
        option["legend"] = {}
    return option["legend"]


def _axis_as_list(axis_value: Any) -> List[Dict[str, Any]]:
    if isinstance(axis_value, list):
        return [dict(ax or {}) for ax in axis_value]
    if isinstance(axis_value, dict):
        return [dict(axis_value)]
    return []


def apply_chart_patch_to_spec(spec: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Apply chart patch operations to an ECharts option dict."""
    if not isinstance(spec, dict):
        return spec
    ops = patch.get("ops")
    if not isinstance(ops, list) or not ops:
        return copy.deepcopy(spec)

    option = copy.deepcopy(spec)

    for op in ops:
        name = op.get("op")
        if name == "set_chart_type":
            value = op.get("value")
            if not isinstance(value, str):
                continue
            value = value.strip()
            if not value:
                continue
            is_area = "area" in value and "bar" not in value
            is_stacked = value in {"stacked_area", "stacked_bar"}
            target_type = (
                "bar"
                if "bar" in value
                else "line"
                if "line" in value or is_area
                else value
            )
            new_series: List[Dict[str, Any]] = []
            for series in option.get("series", []) or []:
                updated = dict(series)
                updated["type"] = target_type
                if is_area:
                    updated["areaStyle"] = {"opacity": 0.2}
                else:
                    updated.pop("areaStyle", None)
                if is_stacked:
                    updated["stack"] = "total"
                else:
                    updated.pop("stack", None)
                new_series.append(updated)
            if new_series:
                option["series"] = new_series
            meta = option.setdefault("meta", {})
            chart_design = meta.setdefault("chartDesign", {})
            chart_design["chart_type"] = value

        elif name == "set_stack":
            stack_enabled = bool(op.get("stack"))
            stack_mode = op.get("mode")
            new_series = []
            for series in option.get("series", []) or []:
                updated = dict(series)
                if stack_enabled:
                    updated["stack"] = "total"
                else:
                    updated.pop("stack", None)
                new_series.append(updated)
            if new_series:
                option["series"] = new_series
            if stack_mode == "percent":
                meta = option.setdefault("meta", {})
                meta["chartValueType"] = "percent"

        elif name == "toggle_series":
            legend = _ensure_legend(option)
            selected = dict(legend.get("selected") or {})
            visible = bool(op.get("visible"))
            for series_name in op.get("names") or []:
                if isinstance(series_name, str):
                    selected[series_name] = visible
            legend["selected"] = selected

        elif name == "set_y_axis_format":
            value_type = op.get("valueType")
            if isinstance(value_type, str) and value_type:
                meta = option.setdefault("meta", {})
                meta["chartValueType"] = value_type

        elif name == "set_x_axis":
            field = op.get("field")
            if isinstance(field, str) and field:
                axes = _axis_as_list(option.get("xAxis"))
                if not axes:
                    axes = [{}]
                updated_axes: List[Dict[str, Any]] = []
                for axis in axes:
                    axis_copy = dict(axis)
                    axis_copy["name"] = field
                    updated_axes.append(axis_copy)
                option["xAxis"] = updated_axes
                meta = option.setdefault("meta", {})
                chart_design = meta.setdefault("chartDesign", {})
                chart_design["x_field"] = field

        elif name == "filter_companies":
            legend = _ensure_legend(option)
            selected = dict(legend.get("selected") or {})
            whitelist = {
                str(ticker).upper()
                for ticker in (op.get("tickers") or [])
                if isinstance(ticker, (str, int, float))
            }
            for series in option.get("series", []) or []:
                series_name = str(series.get("name") or "")
                prefix = series_name.split(" - ", 1)[0].upper()
                selected[series_name] = True if not whitelist else prefix in whitelist
            legend["selected"] = selected

        elif name == "set_palette":
            palette = op.get("palette")
            if isinstance(palette, list) and palette:
                option["color"] = list(palette)

        elif name == "set_axis_scale":
            axis = op.get("axis") or "y"
            scale = op.get("scale")
            axis_type = "log" if scale == "log" else "value"

            def _normalize_axis(axis_value: Dict[str, Any]) -> Dict[str, Any]:
                updated = dict(axis_value or {})
                updated["type"] = axis_type
                return updated

            if axis == "x":
                axes = _axis_as_list(option.get("xAxis"))
                option["xAxis"] = [_normalize_axis(ax) for ax in axes] or [{"type": axis_type}]
            else:
                axes = _axis_as_list(option.get("yAxis"))
                option["yAxis"] = [_normalize_axis(ax) for ax in axes] or [{"type": axis_type}]

        elif name == "select_metrics":
            legend = _ensure_legend(option)
            selected = dict(legend.get("selected") or {})
            include = op.get("include")
            exclude = op.get("exclude")
            include_all = include == "ALL"
            include_set = {str(item) for item in (include or []) if isinstance(item, str)} if isinstance(include, list) else set()
            exclude_set = {str(item) for item in (exclude or []) if isinstance(item, str)} if isinstance(exclude, list) else set()
            for series in option.get("series", []) or []:
                name_str = str(series.get("name") or "")
                metric = name_str.split(" - ", 1)[1] if " - " in name_str else name_str
                if include_all:
                    selected[name_str] = metric not in exclude_set
                elif include_set:
                    selected[name_str] = metric in include_set and metric not in exclude_set
            legend["selected"] = selected

        elif name == "set_grouping":
            grouping = op.get("grouping")
            if isinstance(grouping, str) and grouping:
                meta = option.setdefault("meta", {})
                meta["groupingType"] = grouping

        else:
            continue

    return option

