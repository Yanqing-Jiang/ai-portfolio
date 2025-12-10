"""ECharts Tool for Conversational Analytics - Generate chart specifications."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Tool definition for Claude
ECHARTS_TOOL_DEFINITION = {
    "name": "generate_echarts",
    "description": """Generate an ECharts chart specification to visualize financial data.

Use this tool after querying data to create interactive visualizations.
The generated specification will be rendered as an ECharts chart in the frontend.

Chart types:
- bar: Compare values across categories (companies, quarters)
- line: Show trends over time
- pie: Show composition/distribution
- area: Filled line chart for trends

The tool takes your data and field mappings to generate the complete ECharts option object.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "chart_type": {
                "type": "string",
                "enum": ["bar", "line", "pie", "area"],
                "description": "Type of chart to generate"
            },
            "title": {
                "type": "string",
                "description": "Chart title"
            },
            "data": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Array of data objects from SQL query results"
            },
            "x_field": {
                "type": "string",
                "description": "Field name to use for x-axis (e.g., 'calendar_year', 'ticker')"
            },
            "y_field": {
                "type": "string",
                "description": "Field name to use for y-axis values (e.g., 'value', 'revenue')"
            },
            "series_field": {
                "type": "string",
                "description": "Optional field to group data into multiple series (e.g., 'ticker' for comparing companies)"
            },
            "value_unit": {
                "type": "string",
                "description": "Optional unit hint for y values (e.g., 'millions_usd' for revenue comparisons, 'percentage' for margin charts) to drive labels/tooltip formatting."
            }
        },
        "required": ["chart_type", "data", "x_field", "y_field"]
    }
}

# Color palette for charts
CHART_COLORS = [
    "#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de",
    "#3ba272", "#fc8452", "#9a60b4", "#ea7ccc"
]


def _extract_numeric_values(data: List[Dict[str, Any]], y_field: str) -> List[float]:
    """Function: _extract_numeric_values — used by generate_echarts_spec to gather numeric series values for formatting heuristics."""
    values: List[float] = []
    for row in data:
        value = row.get(y_field, 0)
        if hasattr(value, "__float__"):
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
    return values


def _resolve_value_unit(value_unit: Optional[str], y_field: str, data: List[Dict[str, Any]]) -> str:
    """Function: _resolve_value_unit — called from generate_echarts_spec to determine label units; prefers explicit tool input, then heuristics based on field/metric names."""
    normalized = value_unit.lower() if value_unit else ""

    if not normalized:
        y_lower = y_field.lower()
        metric_text = str(data[0].get("metric", "")).lower() if data else ""
        if any(key in y_lower for key in ["margin", "pct", "percent"]) or "margin" in metric_text:
            normalized = "percentage"
        elif "revenue" in y_lower or "sales" in y_lower or "rev" in metric_text:
            normalized = "millions_usd"
        else:
            normalized = "auto"

    known_units = {"percentage", "millions_usd", "billions_usd"}
    return normalized if normalized in known_units else "auto"


def _build_value_meta(resolved_unit: str, values: List[float]) -> Dict[str, Any]:
    """Function: _build_value_meta — used by generate_echarts_spec to attach formatting hints for the frontend (suffix, decimals, scale)."""
    abs_max = max((abs(v) for v in values), default=0)

    if resolved_unit == "percentage":
        return {
            "unit": "percentage",
            "decimals": 1,
            "suffix": "%",
            "scale": 1,
            "from_ratio": abs_max <= 1.5,
        }

    if resolved_unit == "billions_usd":
        return {
            "unit": "billions_usd",
            "decimals": 1,
            "suffix": "B",
            "scale": 1_000_000_000,
            "from_ratio": False,
        }

    if resolved_unit == "millions_usd":
        return {
            "unit": "millions_usd",
            "decimals": 1,
            "suffix": "M",
            "scale": 1_000_000 if abs_max >= 1_000_000 else 1,
            "from_ratio": False,
        }

    return {
        "unit": "auto",
        "decimals": 1,
        "suffix": "",
        "scale": 1,
        "from_ratio": False,
    }


def generate_echarts_spec(
    chart_type: str,
    data: List[Dict[str, Any]],
    x_field: str,
    y_field: str,
    title: str = "",
    series_field: Optional[str] = None,
    value_unit: Optional[str] = None
) -> Dict[str, Any]:
    """Function: generate_echarts_spec — called from execute_echarts_tool (TOOL_EXECUTORS) to build ECharts options returned to the frontend. Adds value_meta hints so ReactECharts can render data labels/tooltips with correct UOM."""
    if not data:
        return {"title": {"text": title or "No Data"}, "series": []}
    
    values = _extract_numeric_values(data, y_field)
    resolved_unit = _resolve_value_unit(value_unit, y_field, data)
    value_meta = _build_value_meta(resolved_unit, values)

    # Base configuration
    option: Dict[str, Any] = {
        "title": {
            "text": title,
            "left": "center",
            "textStyle": {"color": "#111827"},  # dark text for light background
        },
        "tooltip": {
            "trigger": "axis" if chart_type != "pie" else "item"
        },
        "backgroundColor": "#ffffff",
        "textStyle": {"color": "#111827"},
        "value_meta": value_meta,
    }

    legend_base = {
        "orient": "vertical",
        "right": "2%",
        "top": "middle",
        "textStyle": {"color": "#374151"},
    }
    
    if chart_type == "pie":
        # Pie chart - aggregate by x_field
        pie_data = {}
        for row in data:
            name = str(row.get(x_field, "Unknown"))
            value = row.get(y_field, 0)
            if hasattr(value, '__float__'):
                value = float(value)
            pie_data[name] = pie_data.get(name, 0) + (value or 0)
        
        option["series"] = [{
            "type": "pie",
            "radius": ["40%", "70%"],
            "data": [{"name": k, "value": v} for k, v in pie_data.items()],
            "label": {"color": "#e0e0e0"}
        }]
        option["legend"] = legend_base
        
    else:
        # Bar, line, area charts
        if series_field:
            # Multiple series grouped by series_field
            series_groups: Dict[str, Dict[str, float]] = {}
            x_values = set()
            
            for row in data:
                series_name = str(row.get(series_field, "Unknown"))
                x_val = str(row.get(x_field, ""))
                y_val = row.get(y_field, 0)
                if hasattr(y_val, '__float__'):
                    y_val = float(y_val)
                
                x_values.add(x_val)
                if series_name not in series_groups:
                    series_groups[series_name] = {}
                series_groups[series_name][x_val] = y_val or 0
            
            x_axis_data = sorted(list(x_values))
            series_list = []
            
            for idx, (series_name, values) in enumerate(series_groups.items()):
                series_data = [values.get(x, 0) for x in x_axis_data]
                series_config = {
                    "name": series_name,
                    "type": "line" if chart_type in ["line", "area"] else "bar",
                    "data": series_data,
                    "itemStyle": {"color": CHART_COLORS[idx % len(CHART_COLORS)]}
                }
                if chart_type == "area":
                    series_config["areaStyle"] = {"opacity": 0.3}
                series_list.append(series_config)
            
            option["xAxis"] = {"type": "category", "data": x_axis_data}
            option["yAxis"] = {"type": "value"}
            option["series"] = series_list
            option["legend"] = {**legend_base, "data": list(series_groups.keys())}
            
        else:
            # Single series
            x_axis_data = []
            y_axis_data = []
            
            for row in data:
                x_axis_data.append(str(row.get(x_field, "")))
                y_val = row.get(y_field, 0)
                if hasattr(y_val, '__float__'):
                    y_val = float(y_val)
                y_axis_data.append(y_val or 0)
            
            option["xAxis"] = {"type": "category", "data": x_axis_data}
            option["yAxis"] = {"type": "value"}
            
            series_config = {
                "type": "line" if chart_type in ["line", "area"] else "bar",
                "data": y_axis_data,
                "itemStyle": {"color": CHART_COLORS[0]}
            }
            if chart_type == "area":
                series_config["areaStyle"] = {"opacity": 0.3}
            
            option["series"] = [series_config]
            option["legend"] = {**legend_base, "data": [title or y_field]}
    
    # Add grid for better spacing
    if chart_type != "pie":
        option["grid"] = {"left": "3%", "right": "18%", "bottom": "3%", "containLabel": True}
    
    return option


async def execute_echarts_tool(
    chart_type: str,
    data: List[Dict[str, Any]],
    x_field: str,
    y_field: str,
    title: str = "",
    series_field: Optional[str] = None,
    value_unit: Optional[str] = None
) -> Dict[str, Any]:
    """Function: execute_echarts_tool — called from ConversationalAnalyticsAgent via TOOL_EXECUTORS to return chart configs; forwards value_unit to generate_echarts_spec so the frontend can format labels correctly."""
    try:
        config = generate_echarts_spec(
            chart_type=chart_type,
            data=data,
            x_field=x_field,
            y_field=y_field,
            title=title,
            series_field=series_field,
            value_unit=value_unit,
        )
        
        return {
            "success": True,
            "config": config,
            "chart_type": chart_type
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
