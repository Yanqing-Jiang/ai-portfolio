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
#   Called from: backend.generative_ui.routes.dashboard
#   Invokes: n/a
#   Why: Supports SSE delivery of clarification prompts tied to specific visuals.
# Class: ClarificationResponse
#   Role: Model user responses to clarification prompts.
#   Called from: backend.generative_ui.routes.dashboard
#   Invokes: n/a
#   Why: Keeps response payloads structured for validation.
# Function: build_clarification_for_ambiguous_comparison
#   Role: Build clarification prompt for ambiguous peer comparisons.
#   Called from: backend.generative_ui.routes.dashboard
#   Invokes: ClarificationRequest, ClarificationField
#   Why: Resolves ambiguous comparison intent before rendering visuals.
# Function: build_clarification_for_margin_detail
#   Role: Build clarification prompt for margin analysis specifics.
#   Called from: backend.generative_ui.routes.dashboard
#   Invokes: ClarificationRequest, ClarificationField
#   Why: Lets users specify which margin detail to visualize.
# Function: build_clarification_for_missing_ticker
#   Role: Build clarification prompt when no ticker is detected.
#   Called from: backend.generative_ui.routes.dashboard
#   Invokes: ClarificationRequest, ClarificationField
#   Why: Ensures required ticker inputs are collected.
# Function: clarification_to_sse_event
#   Role: Serialize a clarification request into an SSE event string.
#   Called from: backend.generative_ui.routes.dashboard
#   Invokes: ClarificationRequest.model_dump_json
#   Why: Delivers clarification prompts over the dashboard stream.
# Function: validate_clarification_response
#   Role: Validate user responses against the original request.
#   Called from: backend.generative_ui.routes.dashboard
#   Invokes: n/a
#   Why: Protects plan updates from invalid or unexpected values.
# --- End A2UI Clarification Function/Class Map ---
"""
A2UI Clarification System - LLM-driven pre-generation clarification for ambiguous queries.
"""

from __future__ import annotations

import json
import logging
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
    ClarificationOption(id="1M", label="1 Month", icon="CAL"),
    ClarificationOption(id="3M", label="3 Months", icon="CAL"),
    ClarificationOption(id="6M", label="6 Months", icon="CAL"),
    ClarificationOption(id="1Y", label="1 Year", icon="CAL"),
]

MARGIN_TYPE_OPTIONS = [
    ClarificationOption(id="gross", label="Gross Margin", description="Revenue minus cost of goods sold"),
    ClarificationOption(id="operating", label="Operating Margin", description="Operating income / revenue"),
    ClarificationOption(id="net", label="Net Margin", description="Net income / revenue"),
    ClarificationOption(id="all", label="All Margin Types", description="Show all three margin types"),
]

COMPARISON_TYPE_OPTIONS = [
    ClarificationOption(id="margins", label="Profit Margins", description="Compare gross, operating, net margins", icon="MARG"),
    ClarificationOption(id="revenue", label="Revenue & Growth", description="Compare revenue trends", icon="REV"),
    ClarificationOption(id="stock", label="Stock Performance", description="Compare stock price movements", icon="PRICE"),
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
