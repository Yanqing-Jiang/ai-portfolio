from __future__ import annotations
import uuid
import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple
from .types import IntentModel, QueryPlanModel, ClarifyRequestModel, ClarifyAnswerModel
from .sql_planner import resolve_alias_to_ticker, _sanitize_ticker


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
    
    # 1. Company slot detection
    company_request = _detect_company_slot(intent, template, configs)
    if company_request:
        requests.append(company_request)
    
    # 2. Timeframe slot detection  
    timeframe_request = _detect_timeframe_slot(intent, plan, configs)
    if timeframe_request:
        requests.append(timeframe_request)
    
    # 3. Granularity slot detection
    granularity_request = _detect_granularity_slot(intent, plan)
    if granularity_request:
        requests.append(granularity_request)
    
    # 4. Comparison slot detection
    comparison_request = _detect_comparison_slot(intent, plan, configs)
    if comparison_request:
        requests.append(comparison_request)
    
    # 5. Metrics slot detection (for ambiguous intents)
    metrics_request = _detect_metrics_slot(intent, plan, configs)
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
            resolved = _sanitize_ticker(raw_company, companies)
        
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
    db_config = configs.get('database', {}).get('query_defaults', {})
    min_years = 3
    max_years = db_config.get('max_years_back', 10)
    default_years = db_config.get('default_years_back', 5)
    
    # If timeframe is missing or out of bounds
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
            
            # Validate and sanitize
            companies = configs.get('companies', {}).get('selection_rules', {}).get('default_companies', {}).get('tickers', [])
            valid_ticker = _sanitize_ticker(ticker, companies)
            
            if valid_ticker:
                intent.slots_detected['company'] = valid_ticker
                assumptions.append(f"Using company: {valid_ticker}")
            else:
                # Fallback to first valid company
                fallback = companies[0] if companies else 'NVDA'
                intent.slots_detected['company'] = fallback
                assumptions.append(f"Invalid company selection, using fallback: {fallback}")
        
        elif slot == 'timeframe':
            # Parse timeframe (format: "5 years")
            if isinstance(value, str):
                years_match = [int(s) for s in value.split() if s.isdigit()]
                if years_match:
                    years = years_match[0]
                    # Validate bounds
                    max_years = configs.get('database', {}).get('query_defaults', {}).get('max_years_back', 10)
                    years = max(3, min(years, max_years))
                    plan.timeframe.years_back = years
                    assumptions.append(f"Using timeframe: {years} years")
        
        elif slot == 'granularity':
            # Parse granularity
            gran = str(value).lower()
            if 'quarter' in gran:
                plan.granularity = 'quarterly'
                assumptions.append("Using quarterly granularity")
            else:
                plan.granularity = 'annual'
                assumptions.append("Using annual granularity")
        
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
            assumptions.append(f"Using comparison: {plan.comparison}")
        
        elif slot == 'metrics':
            # Parse metrics selection
            if isinstance(value, list):
                plan.metrics = [str(m).strip() for m in value]
            else:
                plan.metrics = [str(value).strip()]
            assumptions.append(f"Using metrics: {', '.join(plan.metrics)}")
    
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
    
    Calls existing detect_missing_slots early and adds confidence-based
    scope clarification for market share intents. All options/defaults
    come from configs, not LLM suggestions.
    """
    # Use existing logic to detect missing slots
    clarifications = detect_missing_slots(intent, provisional_plan, template, configs)
    
    # Add scope clarification for low-confidence market share
    if intent.confidence < 0.8 and intent.intent_key in ['market_share_single', 'market_share_all']:
        # Only add if not already present
        if not any(c.slot == 'comparison' for c in clarifications):
            # Determine default based on current plan
            default = 'All companies' if provisional_plan.comparison == 'all' else 'Single company only'
            
            clarifications.append(ClarifyRequestModel(
                slot='comparison',
                question='Do you want a single company or all companies?',
                type='single',
                options=['Single company only', 'All companies'],
                default=default,
                reason='Low confidence on scope; please confirm',
                required=True,
                request_id=str(uuid.uuid4()),
                proposed=None,
                proposed_confidence=0.0
            ))
    
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
