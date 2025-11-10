# --- Analytics Function/Class Map ---
# Class: SessionStore
#   Role: Handles SessionStore logic for analytics.core.clarify.
#   Called from: Internal to analytics.core.clarify
#   Collaborators: asyncio.Lock, time.time, asyncio.Condition, asyncio.wait_for
#   Why: Keeps analytics.core.clarify from duplicating SessionStore behavior across flows.
# Function: detect_missing_slots
#   Role: Detect slots that need clarification based on intent, plan, and template requirements.
#   Called from: analytics.flows.planner_executor, tests.analytics.test_clarify_margin, tests.analytics.test_intent_slot_resolution
#   Invokes: analytics.core.clarify._detect_granularity_slot, analytics.core.clarify._detect_margin_metric_slot, analytics.core.clarify._detect_company_slot, analytics.core.clarify._detect_timeframe_slot, +2 more
#   Why: Supports downstream analytics workflows that rely on detect_missing_slots.
# Function: _detect_company_slot
#   Role: Detect if company slot needs clarification.
#   Called from: Internal to analytics.core.clarify
#   Invokes: analytics.core.types.ClarifyRequestModel, analytics.core.companies.resolve_alias_to_ticker, analytics.core.companies.sanitize_ticker, uuid.uuid4
#   Why: Supports downstream analytics workflows that rely on _detect_company_slot.
# Function: _detect_timeframe_slot
#   Role: Detect if timeframe needs clarification.
#   Called from: Internal to analytics.core.clarify
#   Invokes: analytics.core.types.ClarifyRequestModel, uuid.uuid4
#   Why: Supports downstream analytics workflows that rely on _detect_timeframe_slot.
# Function: _detect_granularity_slot
#   Role: Detect if granularity needs clarification.
#   Called from: Internal to analytics.core.clarify
#   Invokes: analytics.core.types.ClarifyRequestModel, uuid.uuid4
#   Why: Supports downstream analytics workflows that rely on _detect_granularity_slot.
# Function: _detect_comparison_slot
#   Role: Detect if comparison type needs clarification.
#   Called from: Internal to analytics.core.clarify
#   Invokes: analytics.core.types.ClarifyRequestModel, uuid.uuid4
#   Why: Supports downstream analytics workflows that rely on _detect_comparison_slot.
# Function: _detect_margin_metric_slot
#   Role: Ensure margin-focused intents capture a specific margin selection.
#   Called from: Internal to analytics.core.clarify
#   Invokes: analytics.core.margins.ensure_margin_choice, analytics.core.margins.list_margin_labels, analytics.core.types.ClarifyRequestModel, uuid.uuid4
#   Why: Supports downstream analytics workflows that rely on _detect_margin_metric_slot.
# Function: _detect_metrics_slot
#   Role: Detect if metrics need clarification for generic/ambiguous intents.
#   Called from: Internal to analytics.core.clarify
#   Invokes: analytics.core.types.ClarifyRequestModel, uuid.uuid4
#   Why: Supports downstream analytics workflows that rely on _detect_metrics_slot.
# Function: merge_answers
#   Role: Validate and merge clarification answers into intent and plan.
#   Called from: analytics.flows.planner_executor, tests.analytics.test_clarify_margin, tests.analytics.test_clarify_timeframe
#   Invokes: analytics.core.companies.get_ticker_list, analytics.core.companies.sanitize_ticker, analytics.core.intent_impl.normalization.normalize_timeframe, analytics.core.intent_impl.normalization.timeframe_implies_quarterly, +2 more
#   Why: Supports downstream analytics workflows that rely on merge_answers.
# Function: get_session_store
#   Role: Get the global session store instance.
#   Called from: analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on get_session_store.
# Function: put_answer
#   Role: Put an answer into the session store.
#   Called from: main
#   Invokes: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on put_answer.
# Function: wait_for_answer
#   Role: Wait for an answer with timeout.
#   Called from: Internal to analytics.core.clarify
#   Invokes: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on wait_for_answer.
# Function: wait_for_answer_blocking
#   Role: Wait for an answer without any timeout (blocks until answered).
#   Called from: analytics.flows.planner_executor
#   Invokes: asyncio.Condition
#   Why: Used when the UX requires explicit user input with no automatic defaulting.
# Function: compute_required_clarifications
#   Role: Wrapper that computes official clarifications deterministically.
#   Called from: analytics.flows.planner_executor, analytics.tools.registry, tests.analytics.test_clarify_comparison
#   Invokes: analytics.core.clarify.detect_missing_slots
#   Why: Applies existing detect_missing_slots logic and enforces deterministic sorting by slot priority.
# Function: validate_clarification_answer
#   Role: Validate that a clarification answer is acceptable for the request.
#   Called from: analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on validate_clarification_answer.
# Function: get_validation_error_message
#   Role: Get detailed error message for invalid clarification answers.
#   Called from: analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on get_validation_error_message.
# --- End Analytics Function/Class Map ---
from __future__ import annotations
import uuid
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set
from .types import IntentModel, QueryPlanModel, ClarifyRequestModel, ClarifyAnswerModel
from .companies import resolve_alias_to_ticker, sanitize_ticker
from .intent_impl.normalization import normalize_timeframe, normalize_metrics, timeframe_implies_quarterly
from .slot_catalog import get_slot_catalog
from .margins import (
    DEFAULT_MARGIN_LABEL,
    apply_margin_choice,
    detect_margin_choice_from_metrics,
    ensure_margin_choice,
    list_margin_labels,
)


# In-memory session store with TTL
class SessionStore:
    def __init__(self):
        self.answers: Dict[str, Dict[str, ClarifyAnswerModel]] = {}
        self.conditions: Dict[str, asyncio.Condition] = {}
        self.expires: Dict[str, float] = {}
        self.lock = asyncio.Lock()
        self.ttl_seconds = 600  # 10 minutes

    async def put_answer(self, answer: ClarifyAnswerModel):
        async with self.lock:
            session_id = answer.session_id
            if session_id not in self.answers:
                self.answers[session_id] = {}
                self.conditions[session_id] = asyncio.Condition()
            
            self.answers[session_id][answer.request_id] = answer
            self.expires[session_id] = time.time() + self.ttl_seconds
            
            print(f"[CLARIFY] Stored answer for session {session_id}, request {answer.request_id}: slot={answer.slot}, value={answer.value}")
            
            # Notify waiting workflow
            async with self.conditions[session_id]:
                self.conditions[session_id].notify_all()

    async def get_answer(self, session_id: str, request_id: str, timeout: float = 10.0) -> Optional[ClarifyAnswerModel]:
        async with self.lock:
            if session_id not in self.conditions:
                self.conditions[session_id] = asyncio.Condition()
                self.answers[session_id] = {}
        
        # Check if answer already exists
        if session_id in self.answers and request_id in self.answers[session_id]:
            return self.answers[session_id][request_id]
        
        # Wait for answer with timeout
        try:
            async with self.conditions[session_id]:
                await asyncio.wait_for(
                    self.conditions[session_id].wait_for(
                        lambda: session_id in self.answers and request_id in self.answers[session_id]
                    ),
                    timeout=timeout
                )
                return self.answers[session_id][request_id]
        except asyncio.TimeoutError:
            return None

    async def cleanup_expired(self):
        async with self.lock:
            now = time.time()
            expired_sessions = [sid for sid, exp_time in self.expires.items() if now > exp_time]
            for session_id in expired_sessions:
                self.answers.pop(session_id, None)
                self.conditions.pop(session_id, None)
                self.expires.pop(session_id, None)


# Global session store instance
_session_store = SessionStore()


def detect_missing_slots(
    intent: IntentModel, 
    plan: QueryPlanModel, 
    template: Optional[Dict[str, Any]], 
    configs: Dict[str, Any]
) -> List[ClarifyRequestModel]:
    """Detect slots that need clarification based on intent, plan, and template requirements."""
    requests = []

    catalog_definition = None
    required_slots: Optional[Set[str]] = None
    if intent and intent.intent_key:
        catalog_definition = get_slot_catalog().get_intent_definition(intent.intent_key)
        if catalog_definition:
            required_slots = {slot.split(".", 1)[0] for slot in catalog_definition.required_slots}

    def _requires(slot_name: str) -> bool:
        if required_slots is None:
            return True
        normalized = slot_name.split(".", 1)[0]
        return normalized in required_slots
    
    # 1. Company slot detection
    if _requires('company'):
        company_request = _detect_company_slot(intent, template, configs)
    else:
        company_request = None
    if company_request:
        requests.append(company_request)
    
    # 2. Timeframe slot detection  
    if _requires('timeframe'):
        timeframe_request = _detect_timeframe_slot(intent, plan, configs)
    else:
        timeframe_request = None
    if timeframe_request:
        requests.append(timeframe_request)
    
    # 3. Granularity slot detection
    granularity_request = _detect_granularity_slot(intent, plan)
    if granularity_request:
        requests.append(granularity_request)
    
    # 4. Comparison slot detection
    if _requires('comparison'):
        comparison_request = _detect_comparison_slot(intent, plan, configs)
    else:
        comparison_request = None
    if comparison_request:
        requests.append(comparison_request)
    
    # 5. Metrics slot detection (for ambiguous intents)
    margin_request = _detect_margin_metric_slot(intent, plan, configs)
    if margin_request:
        requests.append(margin_request)
    metrics_required = (_requires('metric') or _requires('metrics')) and margin_request is None
    metrics_request = _detect_metrics_slot(intent, plan, configs) if metrics_required else None
    if metrics_request:
        requests.append(metrics_request)

    return requests


def _detect_company_slot(
    intent: IntentModel, 
    template: Optional[Dict[str, Any]], 
    configs: Dict[str, Any]
) -> Optional[ClarifyRequestModel]:
    """Detect if company slot needs clarification."""
    # Check if template requires a company
    requires_company = template and '{target_ticker}' in template.get('sql_template', '')
    
    if not requires_company:
        return None
    
    # Check if we already have a valid company
    slots = intent.slots_detected or {}
    raw_company = slots.get('company')
    if raw_company and raw_company not in [None, "None", "null", ""]:
        # Try to resolve it
        companies = configs.get('companies', {}).get('selection_rules', {}).get('default_companies', {}).get('tickers', [])
        resolved = resolve_alias_to_ticker(raw_company, configs)
        if not resolved:
            resolved = sanitize_ticker(raw_company, companies)
        
        if resolved:
            return None  # We have a valid company
    
    # Need clarification
    companies_config = configs.get('companies', {}).get('selection_rules', {}).get('default_companies', {})
    options = companies_config.get('tickers', ['NVDA', 'AMD', 'INTC', 'MU', 'QCOM', 'AVGO', 'TXN'])
    
    # Get company names for better UX
    company_details = configs.get('companies', {}).get('companies', {}).get('semiconductor', [])
    company_map = {comp.get('ticker'): comp.get('short_name', comp.get('ticker')) for comp in company_details if comp.get('ticker')}
    
    display_options = []
    for ticker in options:
        if ticker in company_map:
            display_options.append(f"{ticker} ({company_map[ticker]})")
        else:
            display_options.append(ticker)
    
    # Determine proposed value and confidence
    proposed = None
    confidence = 0.0
    if raw_company:
        proposed = raw_company
        confidence = 0.3  # Low confidence since it didn't resolve
    
    return ClarifyRequestModel(
        slot='company',
        question='Which company would you like to analyze?',
        type='single',
        options=display_options,
        default=f"{options[0]} ({company_map.get(options[0], options[0])})",
        reason='This analysis requires specifying a company',
        required=True,
        request_id=str(uuid.uuid4()),
        proposed=proposed,
        proposed_confidence=confidence
    )


def _detect_timeframe_slot(
    intent: IntentModel,
    plan: QueryPlanModel, 
    configs: Dict[str, Any]
) -> Optional[ClarifyRequestModel]:
    """Detect if timeframe needs clarification."""
    current_years = plan.timeframe.years_back if plan.timeframe else None
    target_year = plan.timeframe.start_year if plan.timeframe else None
    db_config = configs.get('database', {}).get('query_defaults', {})
    min_years = 3
    max_years = db_config.get('max_years_back', 10)
    default_years = db_config.get('default_years_back', 5)

    if intent.intent_key == 'rnd_top_spender':
        if not target_year:
            current_year = datetime.utcnow().year
            options = [str(current_year - offset) for offset in range(0, 6)]
            return ClarifyRequestModel(
                slot='timeframe',
                question='Which fiscal year should we evaluate for the top R&D spender?',
                type='single',
                options=options,
                default=str(current_year),
                reason='Need a specific year to rank R&D spending',
                required=True,
                request_id=str(uuid.uuid4()),
                proposed=str(current_year),
                proposed_confidence=0.6
            )
        return None

    if not current_years or current_years < min_years or current_years > max_years:
        options = ['3 years', '4 years', '5 years', '7 years', '10 years']

        proposed = None
        confidence = 0.0
        if current_years:
            if current_years < min_years:
                proposed = f"{min_years} years"
                confidence = 0.4
            elif current_years > max_years:
                proposed = f"{max_years} years"
                confidence = 0.4

        return ClarifyRequestModel(
            slot='timeframe',
            question='How many years of data would you like to analyze?',
            type='single',
            options=options,
            default=f'{default_years} years',
            reason='Time period needs to be specified' if not current_years else 'Time period is out of valid range',
            required=True,
            request_id=str(uuid.uuid4()),
            proposed=proposed,
            proposed_confidence=confidence
        )

    return None
def _detect_granularity_slot(intent: IntentModel, plan: QueryPlanModel) -> Optional[ClarifyRequestModel]:
    """Detect if granularity needs clarification."""
    current_granularity = plan.granularity
    
    # If granularity is missing or ambiguous
    if not current_granularity or current_granularity not in ['annual', 'quarterly']:
        proposed = None
        confidence = 0.0
        
        # Try to infer from query
        slots = intent.slots_detected or {}
        query_lower = slots.get('original_query', '').lower()
        if 'quarter' in query_lower:
            proposed = 'quarterly'
            confidence = 0.8
        elif 'annual' in query_lower or 'year' in query_lower:
            proposed = 'annual'
            confidence = 0.8
        
        return ClarifyRequestModel(
            slot='granularity',
            question='Would you like annual or quarterly data?',
            type='single', 
            options=['Annual', 'Quarterly'],
            default='Annual',
            reason='Data granularity needs to be specified',
            required=True,
            request_id=str(uuid.uuid4()),
            proposed=proposed,
            proposed_confidence=confidence
        )
    
    return None


def _detect_comparison_slot(
    intent: IntentModel,
    plan: QueryPlanModel,
    configs: Dict[str, Any]
) -> Optional[ClarifyRequestModel]:
    """Detect if comparison type needs clarification."""
    # Only for intents that support multiple comparison types
    multi_variant_intents = {
        'margins_vs_peers': ['vs_peers', 'vs_avg', 'single'],
        'margin_growth_vs_peers': ['vs_peers', 'vs_avg', 'single'],
        # For market share, allow the user to switch scope explicitly
        'market_share_single': ['single', 'all'],
        'market_share_all': ['single', 'all'],
    }
    
    intent_key = intent.intent_key
    if intent_key not in multi_variant_intents:
        return None
    
    current_comparison = plan.comparison
    valid_options = multi_variant_intents[intent_key]
    
    if not current_comparison or current_comparison not in valid_options:
        auto_choice: Optional[str] = None
        slots = intent.slots_detected if isinstance(intent.slots_detected, dict) else {}
        query_lower = str(slots.get('original_query') or '').lower()
        if query_lower:
            if ('average' in query_lower or 'avg' in query_lower) and 'vs_avg' in valid_options:
                auto_choice = 'vs_avg'
            elif ('peer' in query_lower or 'peers' in query_lower) and 'vs_peers' in valid_options:
                auto_choice = 'vs_peers'
            elif 'single' in query_lower and 'single' in valid_options:
                auto_choice = 'single'
        if auto_choice:
            plan.comparison = auto_choice
            if isinstance(intent.slots_detected, dict):
                intent.slots_detected['comparison'] = auto_choice
            return None

        display_options = []
        for option in valid_options:
            if option == 'vs_peers':
                display_options.append('Compare vs peers')
            elif option == 'vs_avg':
                display_options.append('Compare vs average')
            elif option == 'single':
                display_options.append('Single company only')
            elif option == 'all':
                display_options.append('All companies')
            else:
                display_options.append(option.title())
        
        return ClarifyRequestModel(
            slot='comparison',
            question='What type of comparison would you like?',
            type='single',
            options=display_options,
            default=display_options[0],
            reason='Comparison type needs to be specified',
            required=True,
            request_id=str(uuid.uuid4()),
            proposed=None,
            proposed_confidence=0.0
        )
    
    return None


def _detect_margin_metric_slot(
    intent: IntentModel,
    plan: QueryPlanModel,
    configs: Dict[str, Any]
) -> Optional[ClarifyRequestModel]:
    """Ensure margin-focused intents capture a specific margin selection."""
    if intent.intent_key not in {'margins_vs_peers', 'margin_growth_vs_peers'}:
        return None

    slots = intent.slots_detected if isinstance(intent.slots_detected, dict) else {}
    choice = ensure_margin_choice(plan, intent, slots)
    if choice:
        return None

    options = list_margin_labels()
    if not options:
        return None
    default_option = DEFAULT_MARGIN_LABEL if DEFAULT_MARGIN_LABEL in options else options[0]
    return ClarifyRequestModel(
        slot='metric',
        question='Which margin would you like to analyze?',
        type='single',
        options=options,
        default=default_option,
        reason='Margin type (gross, operating, or net) is required for precise SQL and charting.',
        required=True,
        request_id=str(uuid.uuid4()),
        proposed=None,
        proposed_confidence=0.0,
    )


def _detect_metrics_slot(
    intent: IntentModel,
    plan: QueryPlanModel, 
    configs: Dict[str, Any]
) -> Optional[ClarifyRequestModel]:
    """Detect if metrics need clarification for generic/ambiguous intents."""
    # Only clarify metrics for very generic intents with low confidence
    if intent.confidence >= 0.6:
        return None
    
    generic_intents = ['generic_financial_analysis', 'metrics_analysis']
    if intent.intent_key not in generic_intents:
        return None
    
    # If we have specific metrics, no need to clarify
    if plan.metrics and len(plan.metrics) > 0:
        return None
    
    # Curated subset of key metrics
    key_metrics = [
        'Revenue',
        'Net Income', 
        'Operating Income',
        'Gross Profit',
        'R&D Expense',
        'Total Assets',
        'Cash & Equiv.'
    ]
    
    return ClarifyRequestModel(
        slot='metrics',
        question='Which financial metrics would you like to analyze?',
        type='multi',
        options=key_metrics,
        default=key_metrics[:3],  # Revenue, Net Income, Operating Income
        reason='Specific metrics need to be selected for analysis',
        required=True,
        request_id=str(uuid.uuid4()),
        proposed=None,
        proposed_confidence=0.0
    )


async def merge_answers(
    intent: IntentModel,
    plan: QueryPlanModel,
    answers: List[ClarifyAnswerModel],
    configs: Dict[str, Any]
) -> Tuple[IntentModel, QueryPlanModel, List[str]]:
    """Validate and merge clarification answers into intent and plan."""
    assumptions = []
    
    for answer in answers:
        slot = answer.slot
        value = answer.value
        
        if slot == 'company':
            # Parse company selection (format: "NVDA (Nvidia)")
            if isinstance(value, str) and '(' in value:
                ticker = value.split('(')[0].strip()
            else:
                ticker = str(value).strip()

            # Validate and sanitize against configured or default ticker list
            from .companies import get_ticker_list
            companies = get_ticker_list(configs)
            valid_ticker = sanitize_ticker(ticker, companies)

            if valid_ticker:
                intent.slots_detected['company'] = valid_ticker
                assumptions.append(f"Using company: {valid_ticker}")
            else:
                # Fallback to first valid company
                fallback = companies[0] if companies else 'NVDA'
                intent.slots_detected['company'] = fallback
                assumptions.append(f"Invalid company selection, using fallback: {fallback}")

            intent.slots_detected['tickers'] = [intent.slots_detected['company']]

        elif slot == 'timeframe':
            normalized_tf = normalize_timeframe(value, '', configs, origin='clarification')
            if normalized_tf:
                intent.slots_detected['timeframe'] = normalized_tf
                plan.timeframe.years_back = normalized_tf.get('years_back')
                plan.timeframe.quarters_back = normalized_tf.get('quarters_back')
                plan.timeframe.start_year = normalized_tf.get('start_year')
                plan.timeframe.end_year = normalized_tf.get('end_year')
                plan.timeframe.preset = normalized_tf.get('preset')
                plan.timeframe.year_to_date = normalized_tf.get('year_to_date')
                plan.timeframe.source = normalized_tf.get('source')
                plan.timeframe.granularity = normalized_tf.get('granularity')

                if timeframe_implies_quarterly(normalized_tf):
                    plan.granularity = 'quarterly'
                    intent.slots_detected['granularity'] = 'quarterly'
                    assumptions.append('Using quarterly granularity based on requested timeframe')

                descriptor = (
                    normalized_tf.get('preset')
                    or (
                        f"{normalized_tf['years_back']} years"
                        if normalized_tf.get('years_back')
                        else None
                    )
                    or (
                        f"{normalized_tf['quarters_back']} quarters"
                        if normalized_tf.get('quarters_back')
                        else None
                    )
                    or (
                        f"{normalized_tf['start_year']} to {normalized_tf['end_year']}"
                        if normalized_tf.get('start_year') and normalized_tf.get('end_year')
                        else None
                    )
                )
                if descriptor:
                    assumptions.append(f"Using timeframe: {descriptor}")

        elif slot == 'granularity':
            # Parse granularity
            gran = str(value).lower()
            if 'quarter' in gran:
                plan.granularity = 'quarterly'
                assumptions.append("Using quarterly granularity")
            else:
                plan.granularity = 'annual'
                assumptions.append("Using annual granularity")

            intent.slots_detected['granularity'] = plan.granularity
        
        elif slot == 'comparison':
            # Parse comparison type
            comp_str = str(value).lower()
            if 'peers' in comp_str:
                plan.comparison = 'vs_peers'
            elif 'average' in comp_str:
                plan.comparison = 'vs_avg'
            elif 'single' in comp_str:
                plan.comparison = 'single'
                # Update intent key to trigger company requirement
                if 'market_share' in (intent.intent_key or ''):
                    intent.intent_key = 'market_share_single'
                    assumptions.append("Updated intent to market_share_single for company selection")
            elif 'all' in comp_str:
                plan.comparison = 'all'
                # Update intent key for all companies analysis
                if 'market_share' in (intent.intent_key or ''):
                    intent.intent_key = 'market_share_all'
                    assumptions.append("Updated intent to market_share_all")
            intent.slots_detected['comparison'] = plan.comparison
            assumptions.append(f"Using comparison: {plan.comparison}")
        
        elif slot in ('metric', 'metrics'):
            # Parse metrics selection
            normalized_metrics = normalize_metrics(value, configs)
            if not normalized_metrics and value:
                normalized_metrics = [str(value).strip()]
            margin_choice = None
            if normalized_metrics and intent.intent_key in {'margins_vs_peers', 'margin_growth_vs_peers'}:
                margin_choice = detect_margin_choice_from_metrics(normalized_metrics)
                if margin_choice:
                    apply_margin_choice(plan, intent, margin_choice)
            if normalized_metrics and not margin_choice:
                plan.metrics = normalized_metrics
                if isinstance(intent.slots_detected, dict):
                    intent.slots_detected['metrics'] = normalized_metrics
                    intent.slots_detected['metric'] = normalized_metrics[0]
            if plan.metrics:
                assumptions.append(f"Using metrics: {', '.join(plan.metrics)}")
                if margin_choice:
                    assumptions.append(f"Focusing on {margin_choice.label.lower()}")
    
    return intent, plan, assumptions


async def get_session_store() -> SessionStore:
    """Get the global session store instance."""
    return _session_store


async def put_answer(answer: ClarifyAnswerModel):
    """Put an answer into the session store."""
    await _session_store.put_answer(answer)


async def wait_for_answer(session_id: str, request_id: str, timeout: float = 10.0) -> Optional[ClarifyAnswerModel]:
    """Wait for an answer with timeout."""
    return await _session_store.get_answer(session_id, request_id, timeout)


async def wait_for_answer_blocking(session_id: str, request_id: str) -> ClarifyAnswerModel:
    """Wait for an answer without any timeout (blocks until answered).

    Used when the UX requires explicit user input with no automatic
    defaulting. This keeps the event loop non-blocking by awaiting the
    store's condition rather than sleeping.
    """
    # Ensure the condition and answer maps exist
    async with _session_store.lock:
        if session_id not in _session_store.conditions:
            _session_store.conditions[session_id] = asyncio.Condition()
            _session_store.answers[session_id] = {}

    # Return immediately if already present
    if session_id in _session_store.answers and request_id in _session_store.answers[session_id]:
        return _session_store.answers[session_id][request_id]

    async with _session_store.conditions[session_id]:
        await _session_store.conditions[session_id].wait_for(
            lambda: session_id in _session_store.answers and request_id in _session_store.answers[session_id]
        )
        return _session_store.answers[session_id][request_id]


def compute_required_clarifications(
    intent: IntentModel,
    provisional_plan: QueryPlanModel,
    template: Optional[Dict[str, Any]],
    configs: Dict[str, Any]
) -> List[ClarifyRequestModel]:
    """Wrapper that computes official clarifications deterministically.
    
    Applies existing detect_missing_slots logic and enforces deterministic sorting by slot priority.
    All options/defaults come from configs, not LLM suggestions.
    come from configs, not LLM suggestions.
    """
    # Use existing logic to detect missing slots
    clarifications = detect_missing_slots(intent, provisional_plan, template, configs)
    
    # Sort clarifications by priority: comparison > company > granularity > timeframe > metrics
    priority_map = {
        'comparison': 1,
        'company': 2, 
        'granularity': 3,
        'timeframe': 4,
        'metrics': 5
    }
    
    clarifications.sort(key=lambda c: priority_map.get(c.slot, 999))
    
    return clarifications


def validate_clarification_answer(answer: ClarifyAnswerModel, request: ClarifyRequestModel) -> bool:
    """Validate that a clarification answer is acceptable for the request."""
    if request.type == 'single' and answer.value not in request.options:
        # Check if it's a display format (e.g., "NVDA (Nvidia)")
        display_values = [opt.split('(')[0].strip() if '(' in opt else opt for opt in request.options]
        if answer.value not in display_values:
            return False
    elif request.type == 'multi':
        if not isinstance(answer.value, list):
            return False
        for val in answer.value:
            if val not in request.options:
                return False
    
    return True


def get_validation_error_message(answer: ClarifyAnswerModel, request: ClarifyRequestModel) -> Optional[str]:
    """Get detailed error message for invalid clarification answers."""
    if request.type == 'single' and answer.value not in request.options:
        # Check if it's a display format (e.g., "NVDA (Nvidia)")
        display_values = [opt.split('(')[0].strip() if '(' in opt else opt for opt in request.options]
        if answer.value not in display_values:
            return f"Invalid choice '{answer.value}'. Please select one of: {', '.join(request.options)}"
    elif request.type == 'multi':
        if not isinstance(answer.value, list):
            return f"Expected a list for multi-select, but got {type(answer.value).__name__}"
        invalid_values = [val for val in answer.value if val not in request.options]
        if invalid_values:
            return f"Invalid choices: {', '.join(invalid_values)}. Valid options are: {', '.join(request.options)}"
    
    return None





