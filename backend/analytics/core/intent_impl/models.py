from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, ConfigDict

from .normalization import (
    normalize_timeframe,
    normalize_granularity,
    get_default_tickers,
)

class TimeframeModel(BaseModel):
    """Normalized timeframe information shared across analytics flows."""

    model_config = ConfigDict(extra='forbid')

    years_back: Optional[int] = Field(default=4, ge=0, le=10)
    start_year: Optional[int] = None
    end_year: Optional[int] = None


class SlotsModel(BaseModel):
    """Detected slots for analytics intents."""

    model_config = ConfigDict(extra='forbid')

    company: Optional[str] = None
    timeframe: TimeframeModel = Field(default_factory=TimeframeModel)
    metrics: Optional[List[str]] = None
    granularity: Optional[str] = None
    tickers: Optional[List[str]] = None
    comparison: Optional[Literal['single', 'all']] = None
    statistic: Optional[str] = None


class ClarificationSuggestionModel(BaseModel):
    """Advisory clarification suggested by the LLM."""

    model_config = ConfigDict(extra='forbid')

    slot: str = Field(..., description="Slot identifier that needs clarification")
    reason: str = Field(..., description="Why this clarification is required")
    question: Optional[str] = Field(default=None, description="Optional natural language prompt to show the user")
    type: Optional[Literal['single', 'multi', 'free']] = Field(default=None, description="Preferred clarification input type")
    options: List[str] = Field(default_factory=list, description="Suggested options when using single/multi input types")
    proposed: Optional[Any] = Field(default=None, description="LLM-proposed value for this slot")
    proposed_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence in the proposed value")

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


class PossibleIntentModel(BaseModel):
    """Alternative intent interpretation with confidence."""

    model_config = ConfigDict(extra='forbid')

    intent_key: str = Field(..., description="Alternative intent key that could match the query")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence for this alternative intent")


class IntentModel(BaseModel):
    """Runtime intent payload shared between supervisor and memory flows."""

    model_config = ConfigDict(extra='forbid')

    intent_key: Optional[str] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    slots_detected: Dict[str, Any] = Field(default_factory=dict, description="Resolved slot values extracted from the query")
    assumptions: List[str] = Field(default_factory=list)
    clarifications_suggested: List[ClarificationSuggestionModel] = Field(
        default_factory=list,
        description="Hints describing which slots require clarification"
    )
    possible_intents: List[PossibleIntentModel] = Field(
        default_factory=list,
        description="Alternative interpretations with confidence scores"
    )
    intent_reasoning: str = Field(
        default="",
        description="Brief rationale for the chosen intent"
    )


class SqlCriteriaModel(BaseModel):
    """
    Final structured criteria needed to compile & run SQL deterministically.
    """

    model_config = ConfigDict(extra='forbid')

    intent_key: str
    company: Optional[str] = None
    comparison: Optional[Literal['single', 'all']] = None
    timeframe: TimeframeModel = Field(default_factory=TimeframeModel)
    granularity: Literal['annual', 'quarterly'] = 'annual'
    tickers: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    statistic: Optional[str] = None


class LLMClarificationSuggestionModel(BaseModel):
    """Strict clarification suggestion schema for Responses API outputs."""

    model_config = ConfigDict(extra='forbid')

    slot: str
    reason: str
    question: Optional[str] = None
    type: Optional[Literal['single', 'multi', 'free']] = None
    options: List[str] = Field(default_factory=list)
    proposed: Optional[Union[str, int, float, bool, List[str]]] = None
    proposed_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class LLMIntentModel(BaseModel):
    """Structured model used when parsing Responses API intent calls."""

    model_config = ConfigDict(extra='forbid')

    intent_key: Optional[str] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    slots_detected: SlotsModel = Field(default_factory=SlotsModel)
    assumptions: List[str] = Field(default_factory=list)
    clarifications_suggested: List[LLMClarificationSuggestionModel] = Field(default_factory=list)
    possible_intents: List[PossibleIntentModel] = Field(default_factory=list)
    intent_reasoning: str = Field(default="")


class ClarifyRequestModel(BaseModel):
    """Clarification request surfaced to the frontend."""

    slot: str = Field(..., description="Slot needing clarification")
    question: str = Field(..., description="Question to ask the user")
    type: Literal['single', 'multi', 'free'] = Field(..., description="Type of input expected")
    options: List[str] = Field(default_factory=list, description="Available options")
    default: Optional[Any] = Field(default=None, description="Default value if user skips")
    reason: str = Field(default="", description="Why this slot is required")
    required: bool = Field(True, description="Whether this slot is required")
    request_id: str = Field(..., description="Unique clarification request identifier")
    proposed: Optional[Any] = Field(None, description="LLM-proposed value")
    proposed_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    session_id: Optional[str] = Field(default=None, description="Session identifier for routing")


class ClarifyAnswerModel(BaseModel):
    """Clarification answer payload returned from the UI."""

    value: Any
    request_id: str
    slot: str
    session_id: str
    ts: Optional[str] = Field(default=None, description="Timestamp of the answer")


class OffTopicClassifierSchema(BaseModel):
    """Structured output for financial topic classification."""

    model_config = ConfigDict(extra='forbid')

    is_financial_query: bool = Field(..., description="Whether the query is about financial analytics")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the classification")
    topic_category: Literal[
        'financial_analytics',
        'general_conversation',
        'technical_support',
        'personal_questions',
        'other'
    ] = Field(..., description="Detected topic category")
    polite_decline_message: Optional[str] = Field(default=None, description="Polite decline message for off-topic queries")
    suggested_rephrase: Optional[str] = Field(default=None, description="Suggested rephrase to make the query on-topic")



def intent_to_sql_criteria(intent: IntentModel, configs: Dict[str, Any]) -> SqlCriteriaModel:
    """Convert an IntentModel into normalized SQL criteria.

    Ensures downstream SQL compilation receives deterministic slots.
    """
    slots = intent.slots_detected or {}

    company = slots.get('company')

    comparison = slots.get('comparison')
    if comparison not in ("single", "all") and intent.intent_key:
        if intent.intent_key.endswith('_all'):
            comparison = 'all'
        elif intent.intent_key.endswith('_single'):
            comparison = 'single'

    timeframe_slot = slots.get('timeframe')
    if isinstance(timeframe_slot, TimeframeModel):
        timeframe_model = timeframe_slot
    else:
        timeframe_input = timeframe_slot if isinstance(timeframe_slot, dict) else timeframe_slot
        timeframe_data = normalize_timeframe(timeframe_input, '', configs)
        timeframe_model = TimeframeModel(**(timeframe_data or {}))

    granularity = normalize_granularity('', slots.get('granularity'))
    if granularity not in ('annual', 'quarterly'):
        granularity = 'annual'

    raw_tickers = slots.get('tickers')
    if isinstance(raw_tickers, (list, tuple, set)):
        tickers = list(raw_tickers)
    elif raw_tickers:
        tickers = [str(raw_tickers)]
    else:
        tickers = list(get_default_tickers(configs))

    raw_metrics = slots.get('metrics')
    if isinstance(raw_metrics, (list, tuple, set)):
        metrics = list(raw_metrics)
    elif raw_metrics:
        metrics = [str(raw_metrics)]
    else:
        metrics = []

    statistic = slots.get('statistic')
    if isinstance(statistic, str):
        statistic = statistic.strip() or None
    else:
        statistic = None

    return SqlCriteriaModel(
        intent_key=intent.intent_key or '',
        company=company,
        comparison=comparison,
        timeframe=timeframe_model,
        granularity=granularity,
        tickers=tickers,
        metrics=metrics,
        statistic=statistic,
    )
