# --- A2UI Clarification Function/Class Map ---
# Class: ClarificationOption
#   Role: Define selectable clarification option metadata.
#   Called from: build_clarification_for_ambiguous_comparison, build_clarification_for_margin_detail, build_clarification_for_missing_ticker
#   Invokes: n/a
#   Why: Standardizes option payloads for clarification UIs.
# Class: ClarificationField
#   Role: Describe a single clarification prompt field.
#   Called from: build_clarification_for_ambiguous_comparison, build_clarification_for_margin_detail, build_clarification_for_missing_ticker
#   Invokes: n/a
#   Why: Encapsulates the input contract for clarification UI rendering.
# Class: ClarificationRequest
#   Role: Bundle clarification fields with metadata and targeting info.
#   Called from: backend.generative_ui.routes.dashboard, backend.generative_ui.runtime.A2UIRuntime
#   Invokes: n/a
#   Why: Supports SSE delivery of clarification prompts tied to specific visuals.
# Class: ClarificationResponse
#   Role: Model user responses to clarification prompts.
#   Called from: backend.generative_ui.routes.dashboard, backend.generative_ui.runtime.A2UIRuntime
#   Invokes: n/a
#   Why: Keeps response payloads structured for validation.
# Function: build_clarification_for_ambiguous_comparison
#   Role: Build clarification prompt for ambiguous peer comparisons.
#   Called from: backend.generative_ui.routes.dashboard, backend.generative_ui.runtime.A2UIRuntime
#   Invokes: ClarificationRequest, ClarificationField
#   Why: Resolves ambiguous comparison intent before rendering visuals.
# Function: build_clarification_for_margin_detail
#   Role: Build clarification prompt for margin analysis specifics.
#   Called from: backend.generative_ui.routes.dashboard, backend.generative_ui.runtime.A2UIRuntime
#   Invokes: ClarificationRequest, ClarificationField
#   Why: Lets users specify which margin detail to visualize.
# Function: build_clarification_for_missing_ticker
#   Role: Build clarification prompt when no ticker is detected.
#   Called from: backend.generative_ui.routes.dashboard, backend.generative_ui.runtime.A2UIRuntime
#   Invokes: ClarificationRequest, ClarificationField
#   Why: Ensures required ticker inputs are collected.
# Function: clarification_to_sse_event
#   Role: Serialize a clarification request into an SSE event string.
#   Called from: backend.generative_ui.routes.dashboard, backend.generative_ui.runtime.A2UIRuntime
#   Invokes: ClarificationRequest.model_dump_json
#   Why: Delivers clarification prompts over the dashboard stream.
# Function: validate_clarification_response
#   Role: Validate user responses against the original request.
#   Called from: backend.generative_ui.routes.dashboard, backend.generative_ui.runtime.A2UIRuntime
#   Invokes: n/a
#   Why: Protects plan updates from invalid or unexpected values.
# Function: build_visual_clarification
#   Role: Decide if a clarification is needed for the current selection and construct the request.
#   Called from: backend.generative_ui.routes.dashboard, backend.generative_ui.runtime.A2UIRuntime
#   Invokes: build_clarification_for_ambiguous_comparison, build_clarification_for_time_period, build_clarification_for_margin_detail
#   Why: Centralizes clarification heuristics away from the route.
# Function: await_clarification_response
#   Role: Poll dashboard state until a clarification response arrives or times out.
#   Called from: backend.generative_ui.runtime.A2UIRuntime
#   Invokes: asyncio.sleep
#   Why: Lets the runtime pause/resume without blocking the event loop.
# --- End A2UI Clarification Function/Class Map ---
"""
A2UI Clarification System - LLM-driven pre-generation clarification for ambiguous queries.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Literal, Optional, Sequence
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Input types supported by the clarification widget
InputType = Literal["single_choice", "multi_choice", "dropdown", "freeform", "ticker_select", "timeframe_select"]


class ClarificationOption(BaseModel):
    """An option for single/multi choice or dropdown inputs."""
    id: str
    label: str
    description: Optional[str] = None
    icon: Optional[str] = None  # emoji or icon name


class ClarificationField(BaseModel):
    """
    A single clarification input field.
    The LLM decides what type of input to show based on the ambiguity.
    """
    field_id: str = Field(..., description="Unique identifier for this field")
    input_type: InputType = Field(..., description="Type of input widget to render")
    label: str = Field(..., description="Label shown above the input")
    prompt: Optional[str] = Field(None, description="Helper text below the input")
    required: bool = Field(default=True, description="Whether this field is required")
    
    # For single_choice, multi_choice, dropdown
    options: Optional[List[ClarificationOption]] = None
    
    # For freeform input
    placeholder: Optional[str] = None
    
    # Default value
    default: Optional[str] = None


class ClarificationRequest(BaseModel):
    """
    A complete clarification request with one or more input fields.
    Emitted by the agent when pre-generation clarification is needed.
    """
    request_id: str = Field(..., description="Unique ID for this request (used to match responses)")
    title: str = Field(default="Quick clarification needed", description="Card title")
    subtitle: Optional[str] = Field(None, description="Optional subtitle explaining why clarification is needed")
    fields: List[ClarificationField] = Field(..., description="List of input fields")
    timeout_seconds: int = Field(default=120, description="Auto-cancel timeout")
    skip_allowed: bool = Field(default=True, description="Whether user can skip and let LLM decide")
    target_component_id: Optional[str] = Field(
        default=None,
        description="Optional A2UI component ID to anchor clarification UI",
    )


class ClarificationResponse(BaseModel):
    """User's response to a clarification request."""
    request_id: str
    values: Dict[str, Any]  # field_id -> value(s)
    skipped: bool = False


# Predefined options for common clarification types
TIMEFRAME_OPTIONS = [
    ClarificationOption(id="1M", label="1 Month", icon="📅"),
    ClarificationOption(id="3M", label="3 Months", icon="📅"),
    ClarificationOption(id="6M", label="6 Months", icon="📅"),
    ClarificationOption(id="1Y", label="1 Year", icon="📅"),
]

MARGIN_TYPE_OPTIONS = [
    ClarificationOption(id="gross", label="Gross Margin", description="Revenue minus cost of goods sold"),
    ClarificationOption(id="operating", label="Operating Margin", description="Operating income / revenue"),
    ClarificationOption(id="net", label="Net Margin", description="Net income / revenue"),
    ClarificationOption(id="all", label="All Margin Types", description="Show all three margin types"),
]

COMPARISON_TYPE_OPTIONS = [
    ClarificationOption(id="margins", label="Profit Margins", description="Compare gross, operating, net margins", icon="📊"),
    ClarificationOption(id="revenue", label="Revenue & Growth", description="Compare revenue trends", icon="💰"),
    ClarificationOption(id="stock", label="Stock Performance", description="Compare stock price movements", icon="📈"),
]

PERIOD_OPTIONS = [
    ClarificationOption(id="quarterly", label="Quarterly", description="Show quarterly breakdown"),
    ClarificationOption(id="annual", label="Annual", description="Show annual figures"),
]


def build_clarification_for_ambiguous_comparison(
    tickers: Sequence[str],
    question: str,
    request_id: str,
    target_component_id: Optional[str] = None,
) -> ClarificationRequest:
    """
    Generate clarification request when comparing tickers but comparison type is ambiguous.
    
    Called from: agent_v2.py when skill selection detects ambiguity
    """
    return ClarificationRequest(
        request_id=request_id,
        title=f"Comparing {', '.join(tickers)}",
        subtitle="What would you like to compare?",
        target_component_id=target_component_id,
        fields=[
            ClarificationField(
                field_id="comparison_type",
                input_type="single_choice",
                label="Comparison type",
                options=COMPARISON_TYPE_OPTIONS,
                required=True,
            ),
            ClarificationField(
                field_id="period",
                input_type="dropdown",
                label="Time period",
                options=PERIOD_OPTIONS,
                default="quarterly",
                required=False,
            ),
        ],
        skip_allowed=True,
    )


def build_clarification_for_margin_detail(
    ticker: str,
    request_id: str,
    target_component_id: Optional[str] = None,
) -> ClarificationRequest:
    """
    Generate clarification request when margin analysis needs more specificity.
    
    Called from: agent_v2.py when margin analysis could use user guidance
    """
    return ClarificationRequest(
        request_id=request_id,
        title=f"{ticker} Margin Analysis",
        subtitle="Customize your analysis",
        target_component_id=target_component_id,
        fields=[
            ClarificationField(
                field_id="margin_types",
                input_type="multi_choice",
                label="Margin types to display",
                options=MARGIN_TYPE_OPTIONS,
                default="all",
                required=False,
            ),
            ClarificationField(
                field_id="timeframe",
                input_type="dropdown",
                label="Chart timeframe",
                options=TIMEFRAME_OPTIONS,
                default="3M",
                required=False,
            ),
        ],
        skip_allowed=True,
    )


def build_clarification_for_time_period(
    ticker: str,
    request_id: str,
    target_component_id: Optional[str] = None,
) -> ClarificationRequest:
    """
    Generate clarification request for ambiguous time period (e.g., "recently").
    
    Called from: dashboard.py when explain_move skill has temporal ambiguity
    """
    time_period_options = [
        ClarificationOption(id="1W", label="Last Week", description="Past 7 days", icon="📅"),
        ClarificationOption(id="1M", label="Last Month", description="Past 30 days", icon="📅"),
        ClarificationOption(id="3M", label="Last Quarter", description="Past 3 months", icon="📅"),
        ClarificationOption(id="YTD", label="Year to Date", description="Since January 1st", icon="📅"),
    ]
    
    return ClarificationRequest(
        request_id=request_id,
        title=f"What time period for {ticker}?",
        subtitle="Help us narrow down the analysis",
        target_component_id=target_component_id,
        fields=[
            ClarificationField(
                field_id="time_period",
                input_type="single_choice",
                label="Select a time period",
                options=time_period_options,
                default="1M",
                required=False,
            ),
        ],
        skip_allowed=True,
    )


def build_clarification_for_missing_ticker(
    question: str,
    request_id: str,
    available_tickers: Sequence[str],
    target_component_id: Optional[str] = None,
) -> ClarificationRequest:
    """
    Generate clarification request when no ticker could be extracted.
    
    Called from: agent_v2.py when skill selection finds no tickers
    """
    ticker_options = [
        ClarificationOption(id=t, label=t, description=f"Analyze {t}")
        for t in available_tickers
    ]
    
    return ClarificationRequest(
        request_id=request_id,
        title="Which company?",
        subtitle="Please select or enter a ticker symbol",
        target_component_id=target_component_id,
        fields=[
            ClarificationField(
                field_id="ticker",
                input_type="single_choice",
                label="Select a company",
                options=ticker_options,
                required=False,
            ),
            ClarificationField(
                field_id="custom_ticker",
                input_type="freeform",
                label="Or enter a ticker",
                placeholder="e.g., AAPL, MSFT",
                required=False,
            ),
        ],
        skip_allowed=False,  # Must have a ticker
    )


def clarification_to_sse_event(clarification: ClarificationRequest) -> str:
    """Convert a clarification request to an SSE event string."""
    return f"event: clarification_request\ndata: {clarification.model_dump_json()}\n\n"


# -----------------------------------------------------------------------------
# LLM-Driven Clarification Generator
# -----------------------------------------------------------------------------

# Hardcoded from DB schema (these don't change)
AVAILABLE_TICKERS = ["AMD", "NVDA", "INTC", "QCOM", "MU", "AVGO", "TXN"]
AVAILABLE_METRICS = ["Revenue", "Gross Margin", "Operating Margin", "Net Margin", "EPS", "Free Cash Flow"]


async def generate_clarification_with_llm(
    question: str,
    skill_id: str,
    tickers: List[str],
    request_id: str,
) -> ClarificationRequest:
    """
    Generate ticker-aware clarification options using LLM.

    Called from: build_visual_clarification()
    Why: Dynamic options that reference actual tickers, not hardcoded generic text

    NOTE: skill_id is passed for CONTEXT ONLY - LLM should NOT generate skill changes.
    """
    from .sdk_wrapper import get_sdk_wrapper

    wrapper = get_sdk_wrapper()
    if not wrapper.is_initialized:
        await wrapper.initialize()

    tickers_str = ", ".join(tickers) if tickers else "no specific tickers"

    # Combined prompt (system + user context) for single query
    prompt = f"""You generate clarification prompts for a financial analytics dashboard.

AVAILABLE TICKERS: {", ".join(AVAILABLE_TICKERS)}
AVAILABLE METRICS: {", ".join(AVAILABLE_METRICS)}

Context:
- User question: "{question}"
- Current skill: {skill_id} (for context only - DO NOT suggest changing this)
- Detected tickers: {tickers_str}

Generate a clarification to help the user specify their analysis parameters.

Rules:
1. Title should mention the actual tickers (e.g., "Comparing NVDA, AMD")
2. field_id MUST be one of: "metric", "time_range", "tickers"
3. Option id values:
   - For metric: use exact metric names from AVAILABLE METRICS
   - For time_range: use "1M", "3M", "6M", "1Y", "3Y"
   - For tickers: use ticker symbols from AVAILABLE TICKERS
4. Make descriptions ticker-specific (e.g., "NVDA vs AMD revenue growth")
5. Include 2-4 options per field
6. Use emoji icons

Output ONLY valid JSON (no markdown, no explanation) with this structure:
{{
  "title": "string",
  "subtitle": "string (optional)",
  "fields": [
    {{
      "field_id": "metric" | "time_range" | "tickers",
      "input_type": "single_choice" | "multi_choice",
      "label": "string",
      "options": [
        {{"id": "string", "label": "string", "description": "string (optional)", "icon": "string (optional)"}}
      ]
    }}
  ]
}}

Generate clarification for: "{question}" with tickers: {tickers_str}"""

    try:
        response = await wrapper.query(
            prompt=prompt,
            max_tokens=1024,
            temperature=0.3,
        )

        if response.error:
            logger.warning("LLM clarification generation failed: %s, falling back to defaults", response.error)
            return _fallback_clarification(question, skill_id, tickers, request_id)

        # Parse JSON from response
        text = response.content
        # Handle potential markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        data = json.loads(text.strip())

        fields = [
            ClarificationField(
                field_id=f["field_id"],
                input_type=f["input_type"],
                label=f["label"],
                options=[
                    ClarificationOption(
                        id=opt["id"],
                        label=opt["label"],
                        description=opt.get("description"),
                        icon=opt.get("icon")
                    )
                    for opt in f.get("options", [])
                ]
            )
            for f in data.get("fields", [])
        ]

        return ClarificationRequest(
            request_id=request_id,
            title=data.get("title", f"Clarify: {question[:50]}"),
            subtitle=data.get("subtitle"),
            fields=fields,
        )

    except json.JSONDecodeError as e:
        logger.warning("Failed to parse LLM clarification JSON: %s", e)
        return _fallback_clarification(question, skill_id, tickers, request_id)
    except Exception as e:
        logger.error("LLM clarification generation error: %s", e)
        return _fallback_clarification(question, skill_id, tickers, request_id)


def _fallback_clarification(
    question: str,
    skill_id: str,
    tickers: List[str],
    request_id: str,
) -> ClarificationRequest:
    """
    Fallback to hardcoded clarification when LLM fails.

    Called from: generate_clarification_with_llm() on error
    Why: Ensures clarification still works even when LLM is unavailable
    """
    tickers_str = ", ".join(tickers) if tickers else "stocks"

    if skill_id == "a2ui_peer_compare":
        return ClarificationRequest(
            request_id=request_id,
            title=f"Comparing {tickers_str}",
            subtitle="What would you like to compare?",
            fields=[
                ClarificationField(
                    field_id="metric",
                    input_type="single_choice",
                    label="Metric to compare",
                    options=[
                        ClarificationOption(id="Revenue", label="Revenue", icon="💰"),
                        ClarificationOption(id="Gross Margin", label="Gross Margin", icon="📊"),
                        ClarificationOption(id="Operating Margin", label="Operating Margin", icon="⚙️"),
                    ],
                ),
            ],
        )
    elif skill_id == "a2ui_explain_move":
        ticker = tickers[0] if tickers else "stock"
        return ClarificationRequest(
            request_id=request_id,
            title=f"Analyzing {ticker}",
            subtitle="What time period?",
            fields=[
                ClarificationField(
                    field_id="time_range",
                    input_type="single_choice",
                    label="Time period",
                    options=[
                        ClarificationOption(id="1M", label="Last Month", icon="📅"),
                        ClarificationOption(id="3M", label="Last Quarter", icon="📅"),
                        ClarificationOption(id="1Y", label="Last Year", icon="📅"),
                    ],
                ),
            ],
        )
    else:
        # Generic fallback
        return ClarificationRequest(
            request_id=request_id,
            title="Clarify your request",
            fields=[
                ClarificationField(
                    field_id="metric",
                    input_type="single_choice",
                    label="What to analyze?",
                    options=[
                        ClarificationOption(id="Revenue", label="Revenue", icon="💰"),
                        ClarificationOption(id="Gross Margin", label="Margins", icon="📊"),
                    ],
                ),
            ],
        )


def validate_clarification_response(
    response: ClarificationResponse,
    original_request: ClarificationRequest,
) -> Dict[str, Any]:
    """
    Validate and extract values from a clarification response.
    
    Returns a normalized dict of field_id -> validated value(s).
    """
    validated = {}
    field_map = {f.field_id: f for f in original_request.fields}
    
    for field_id, value in response.values.items():
        if field_id not in field_map:
            continue
        
        field = field_map[field_id]
        
        # Validate based on input type
        if field.input_type in ("single_choice", "dropdown"):
            if field.options and value not in [o.id for o in field.options]:
                continue  # Invalid option
            validated[field_id] = value
            
        elif field.input_type == "multi_choice":
            if isinstance(value, list) and field.options:
                valid_ids = [o.id for o in field.options]
                validated[field_id] = [v for v in value if v in valid_ids]
            else:
                validated[field_id] = [value] if value else []
                
        elif field.input_type == "freeform":
            validated[field_id] = str(value).strip() if value else ""
            
        else:
            validated[field_id] = value
    
    return validated


# -----------------------------------------------------------------------------
# Runtime-oriented helpers (moved from dashboard route for reuse)
# -----------------------------------------------------------------------------

COMPARISON_KEYWORDS = ("revenue", "margin", "profit", "stock", "price", "earnings", "eps", "income", "growth")
MARGIN_KEYWORDS = ("gross", "operating", "net")
TEMPORAL_KEYWORDS = ("recently", "lately", "past", "last", "previous")
EXPLICIT_PERIOD_KEYWORDS = ("week", "month", "quarter", "year", "1m", "3m", "6m", "1y", "ytd")


def _needs_peer_compare_clarification(question: str, plan: Dict[str, Any], params: Dict[str, Any]) -> bool:
    """Return True when peer comparisons need metric clarification."""
    if params.get("clarified") or params.get("pending_clarification"):
        return False
    # Only for peer compare skill
    skill_id = plan.get("skill_id", "")
    if skill_id != "a2ui_peer_compare":
        return False
    question_lower = question.lower()
    if not any(token in question_lower for token in ("compare", "vs", "versus")):
        return False
    # Use word boundary matching to avoid false positives (e.g., "stocks" matching "stock")
    words = set(re.findall(r'\b\w+\b', question_lower))
    return not any(keyword in words for keyword in COMPARISON_KEYWORDS)


def _needs_explain_move_period_clarification(question: str, plan: Dict[str, Any], params: Dict[str, Any]) -> bool:
    """Return True when explain_move needs period clarification (e.g., 'recently')."""
    if params.get("clarified") or params.get("pending_clarification"):
        return False
    if plan.get("time_period"):
        return False
    question_lower = question.lower()
    has_temporal = any(token in question_lower for token in TEMPORAL_KEYWORDS)
    has_explicit_period = any(token in question_lower for token in EXPLICIT_PERIOD_KEYWORDS)
    return has_temporal and not has_explicit_period


def _needs_margin_clarification(question: str, plan: Dict[str, Any], params: Dict[str, Any]) -> bool:
    """Return True when margin analysis needs more specificity."""
    if params.get("clarified") or params.get("pending_clarification"):
        return False
    if plan.get("margin_types"):
        return False
    question_lower = question.lower()
    if "margin" not in question_lower:
        return False
    return not any(token in question_lower for token in MARGIN_KEYWORDS)


async def build_visual_clarification(
    question: str,
    selection: Any,
    plan: Dict[str, Any],
    params: Dict[str, Any],
) -> Optional[ClarificationRequest]:
    """
    Decide whether a visual-specific clarification is needed and build it via LLM.

    Called from: dashboard route and runtime orchestrator.
    Why: Uses LLM to generate ticker-aware options instead of hardcoded generic text.
    """
    needs_clarification = False

    if selection.skill_id == "a2ui_peer_compare" and _needs_peer_compare_clarification(question, plan, params):
        needs_clarification = True
    elif selection.skill_id == "a2ui_explain_move" and _needs_explain_move_period_clarification(question, plan, params):
        needs_clarification = True
    elif selection.skill_id == "a2ui_margin_analysis" and _needs_margin_clarification(question, plan, params):
        needs_clarification = True

    if not needs_clarification:
        return None

    # Generate clarification via LLM for ticker-aware options
    request_id = f"clarify_{selection.skill_id}_{time.time_ns()}"
    return await generate_clarification_with_llm(
        question=question,
        skill_id=selection.skill_id,
        tickers=selection.tickers,
        request_id=request_id,
    )


async def await_clarification_response(
    state: Any,
    request_id: str,
    timeout_seconds: int,
    poll_interval: float = 0.25,
) -> Dict[str, Any]:
    """
    Poll the dashboard state for a clarification response or timeout.
    """
    deadline = time.monotonic() + max(timeout_seconds, 1)

    while time.monotonic() < deadline:
        responses = state.params.get("clarification_responses") or {}
        if isinstance(responses, dict) and request_id in responses:
            return responses[request_id]
        await asyncio.sleep(poll_interval)

    # Timeout: mark skipped
    responses = state.params.get("clarification_responses") or {}
    responses[request_id] = {"values": {}, "skipped": True}
    state.update_params({"clarification_responses": responses})
    return responses[request_id]
