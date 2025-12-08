# --- Analytics Function/Class Map ---
# Functions: is_chart_revision_query, infer_chart_patch_from_query
#   Role: Detect chart revision intent and build patch ops from user queries.
#   Called from: analytics.core.charting.revision_emitters, analytics.flows.chart_revision facade, multi_agent flow
#   Invokes: normalize helpers below
# Functions: is_analysis_revision_query, infer_analysis_revision_from_query
#   Role: Detect analysis revision intent and extract revision focus payload.
#   Called from: analytics.core.charting.revision_emitters, analytics.flows.chart_revision facade, multi_agent flow
#   Invokes: _clean_revision_snippet, regexes
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

REVISION_KEYWORDS = (
    "revise",
    "revise chart",
    "update",
    "change",
    "modify",
    "tweak",
    "adjust",
    "convert",
    "switch",
    "turn",
    "make",
)

ANALYSIS_REVISION_KEYWORDS = (
    "analysis",
    "summary",
    "rewrite",
    "revise",
    "update",
    "insight",
    "insights",
)

ANALYSIS_REVISION_ANCHORS = ("analysis", "summary", "insight", "insights")

ANALYSIS_TEXT_MARKERS = (
    "analysis:",
    "analysis ->",
    "summary:",
    "summary ->",
    "rewrite analysis",
    "rewrite the analysis to",
    "rewrite the analysis:",
    "update analysis to",
    "revise analysis to",
    "redo the analysis to",
    "redo the analysis:",
    "redo the analysis and",
    "redo the analysis but",
    "replace analysis with",
    "analysis focus:",
)

ANALYSIS_REVISION_REGEXES: List[re.Pattern[str]] = [
    re.compile(
        r"(?:redo|refresh|revise|rewrite|update)\s+the\s+analysis(?:\s+but|\s+and)?(?:\s+to)?\s+(?:focus|highlight|emphasize|emphasise)\s+(?:on\s+)?(?P<payload>.+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:focus|refocus)\s+the\s+analysis\s+on\s+(?P<payload>.+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"analysis(?:\s+should|\s+needs|\s+must)?\s+(?:now\s+)?(?:focus|highlight|emphasize|emphasise)\s+(?:on\s+)?(?P<payload>.+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:please\s+)?rewrite\s+the\s+analysis\s+around\s+(?P<payload>.+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"analysis\s+focus:\s*(?P<payload>.+)",
        re.IGNORECASE,
    ),
]

CHART_TYPE_SYNONYMS: Dict[str, List[str]] = {
    "bar": ["bar chart", "bar", "column chart"],
    "line": ["line chart", "line", "sparkline"],
    "area": ["area chart", "area"],
    "stacked_bar": ["stacked bar", "stacked column"],
    "stacked_area": ["stacked area"],
}


def _clean_revision_snippet(snippet: str) -> Optional[str]:
    candidate = snippet.strip().strip('"\'. ')
    if not candidate:
        return None
    parts = re.split(r"[.!?](?:\s|$)", candidate, maxsplit=1)
    candidate = parts[0].strip()
    if not candidate:
        return None
    for suffix in ("please", "thanks", "thank you"):
        if candidate.lower().endswith(f" {suffix}"):
            candidate = candidate[: -(len(suffix) + 1)].strip()
    return candidate or None


def is_analysis_revision_query(query: Optional[str]) -> bool:
    if not query:
        return False
    normalized = query.strip().lower()
    if not any(anchor in normalized for anchor in ANALYSIS_REVISION_ANCHORS):
        return False
    return any(marker in normalized for marker in ANALYSIS_REVISION_KEYWORDS)


def infer_analysis_revision_from_query(query: str) -> Optional[str]:
    normalized = query.strip()
    lower = normalized.lower()
    for marker in ANALYSIS_TEXT_MARKERS:
        idx = lower.find(marker)
        if idx != -1:
            start = idx + len(marker)
            candidate = normalized[start:].strip().lstrip(":").strip()
            cleaned = _clean_revision_snippet(candidate)
            if cleaned:
                return cleaned
    if '"' in normalized:
        segments = [segment.strip() for segment in normalized.split('"') if segment.strip()]
        if len(segments) >= 2:
            cleaned = _clean_revision_snippet(segments[-1])
            if cleaned:
                return cleaned
    for pattern in ANALYSIS_REVISION_REGEXES:
        match = pattern.search(normalized)
        if not match:
            continue
        payload = match.group("payload") if "payload" in match.groupdict() else match.group(1)
        if not payload:
            continue
        cleaned = _clean_revision_snippet(payload)
        if cleaned:
            return cleaned
    prefixes = (
        "redo the analysis",
        "rewrite the analysis",
        "revise the analysis",
        "refresh the analysis",
        "update the analysis",
    )
    for prefix in prefixes:
        if lower.startswith(prefix):
            remainder = normalized[len(prefix):].strip(" :,-")
            cleaned = _clean_revision_snippet(remainder) if remainder else None
            if cleaned:
                return cleaned
    return None


def is_chart_revision_query(query: Optional[str]) -> bool:
    if not query:
        return False
    normalized = query.strip().lower()
    if "chart" not in normalized:
        return False
    return any(keyword in normalized for keyword in REVISION_KEYWORDS)


def infer_chart_patch_from_query(query: str) -> Optional[Dict[str, Any]]:
    normalized = query.lower()
    ops: List[Dict[str, Any]] = []

    def _match_type(chart_type: str) -> bool:
        synonyms = CHART_TYPE_SYNONYMS.get(chart_type, [])
        return any(phrase in normalized for phrase in synonyms)

    if _match_type("stacked_bar"):
        ops.append({"op": "set_chart_type", "value": "stacked_bar"})
    elif _match_type("stacked_area"):
        ops.append({"op": "set_chart_type", "value": "stacked_area"})
    elif _match_type("bar"):
        ops.append({"op": "set_chart_type", "value": "bar"})
    elif _match_type("area"):
        ops.append({"op": "set_chart_type", "value": "area"})
    elif _match_type("line"):
        ops.append({"op": "set_chart_type", "value": "line"})

    if "stack" in normalized:
        mode = "percent" if any(token in normalized for token in ("percent", "percentage", "100%")) else "normal"
        ops.append({"op": "set_stack", "stack": True, "mode": mode})

    if "percent" in normalized and not any(op.get("op") == "set_y_axis_format" for op in ops):
        ops.append({"op": "set_y_axis_format", "valueType": "percent"})

    if not ops:
        return None

    return {"ops": ops}

