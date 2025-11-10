# --- Analytics Function/Class Map ---
# Function: _is_ranking_query
#   Role: Handles is ranking query logic for analytics.core.intent_impl.detection.
#   Called from: Internal to analytics.core.intent_impl.detection
#   Invokes: Internal helpers only
#   Why: Keeps analytics.core.intent_impl.detection from duplicating is ranking query behavior across flows.
# Function: _build_company_clarification
#   Role: Handles build company clarification logic for analytics.core.intent_impl.detection.
#   Called from: Internal to analytics.core.intent_impl.detection
#   Invokes: analytics.core.intent_impl.models.ClarificationSuggestionModel
#   Why: Keeps analytics.core.intent_impl.detection from duplicating build company clarification behavior across flows.
# Function: heuristic_intent
#   Role: Simple keyword-based intent detection used as a lightweight fallback.
#   Called from: analytics.core.intent, analytics.core.intent_impl, tests.analytics.test_intent_ranking
#   Invokes: analytics.core.intent_impl.normalization.get_default_tickers, analytics.core.intent_impl.detection.detect_companies_from_query, analytics.core.intent_impl.normalization.normalize_timeframe, analytics.core.intent_impl.detection.post_process_slots, +2 more
#   Why: Supports downstream analytics workflows that rely on heuristic_intent.
# Function: _clone_slot_option
#   Role: Handles clone slot option logic for analytics.core.intent_impl.detection.
#   Called from: Internal to analytics.core.intent_impl.detection
#   Invokes: analytics.core.slot_catalog.SlotOption
#   Why: Keeps analytics.core.intent_impl.detection from duplicating clone slot option behavior across flows.
# Function: _select_candidate_definitions
#   Role: Handles select candidate definitions logic for analytics.core.intent_impl.detection.
#   Called from: Internal to analytics.core.intent_impl.detection
#   Invokes: Internal helpers only
#   Why: Keeps analytics.core.intent_impl.detection from duplicating select candidate definitions behavior across flows.
# Function: detect_company_from_query
#   Role: Detect a company from free-form text using alias and ticker matching.
#   Called from: analytics.core.intent, analytics.core.intent_impl
#   Invokes: analytics.core.intent_impl.normalization.get_default_tickers, re.findall
#   Why: Supports downstream analytics workflows that rely on detect_company_from_query.
# Function: detect_companies_from_query
#   Role: Return all distinct company tickers referenced in the query.
#   Called from: Internal to analytics.core.intent_impl.detection
#   Invokes: re.findall, analytics.core.intent_impl.normalization.get_default_tickers
#   Why: Supports downstream analytics workflows that rely on detect_companies_from_query.
# Function: _normalize_company_candidates
#   Role: Return upper-cased company symbols ordered by their appearance in the query.
#   Called from: Internal to analytics.core.intent_impl.detection
#   Invokes: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on _normalize_company_candidates.
# Function: post_process_slots
#   Role: Normalise detected slots using shared heuristics.
#   Called from: analytics.core.intent, analytics.core.intent_impl, analytics.flows.planner_executor, tests.analytics.test_intent_post_process
#   Invokes: analytics.core.intent_impl.detection._normalize_company_candidates, analytics.core.intent_impl.detection.detect_companies_from_query, analytics.core.intent_impl.normalization.normalize_timeframe, analytics.core.intent_impl.normalization.normalize_granularity, +2 more
#   Why: Supports downstream analytics workflows that rely on post_process_slots.
# Function: cleanup_clarifications_after_company_detection
#   Role: Drop redundant clarifications once a company has been inferred.
#   Called from: analytics.core.intent, analytics.core.intent_impl
#   Invokes: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on cleanup_clarifications_after_company_detection.
# Function: _ensure_required_slots
#   Role: Handles ensure required slots logic for analytics.core.intent_impl.detection.
#   Called from: Internal to analytics.core.intent_impl.detection
#   Invokes: analytics.core.intent_impl.detection._clone_slot_option, analytics.core.intent_impl.models.SlotStatusModel
#   Why: Keeps analytics.core.intent_impl.detection from duplicating ensure required slots behavior across flows.
# Function: _append_missing_followups
#   Role: Handles append missing followups logic for analytics.core.intent_impl.detection.
#   Called from: Internal to analytics.core.intent_impl.detection
#   Invokes: analytics.core.intent_impl.detection._slot_has_value, analytics.core.intent_impl.detection._clone_slot_option, analytics.core.intent_impl.models.FollowUpModel
#   Why: Keeps analytics.core.intent_impl.detection from duplicating append missing followups behavior across flows.
# Function: _slot_has_value
#   Role: Handles slot has value logic for analytics.core.intent_impl.detection.
#   Called from: Internal to analytics.core.intent_impl.detection
#   Invokes: analytics.core.intent_impl.detection._slot_has_value
#   Why: Keeps analytics.core.intent_impl.detection from duplicating slot has value behavior across flows.
# Function: _normalize_metric_slot_statuses
#   Role: Handles normalize metric slot statuses logic for analytics.core.intent_impl.detection.
#   Called from: Internal to analytics.core.intent_impl.detection
#   Invokes: analytics.core.intent_impl.detection._slot_has_value
#   Why: Keeps analytics.core.intent_impl.detection from duplicating normalize metric slot statuses behavior across flows.
# Function: _fallback_intent_resolution
#   Role: Handles fallback intent resolution logic for analytics.core.intent_impl.detection.
#   Called from: Internal to analytics.core.intent_impl.detection
#   Invokes: analytics.core.intent_impl.models.IntentSelectionModel, analytics.core.intent_impl.normalization.normalize_metrics, analytics.core.intent_impl.models.IntentResolutionModel, analytics.core.intent_impl.detection.detect_company_from_query, +2 more
#   Why: Keeps analytics.core.intent_impl.detection from duplicating fallback intent resolution behavior across flows.
# Function: _llm_resolution_to_runtime
#   Role: Handles llm resolution to runtime logic for analytics.core.intent_impl.detection.
#   Called from: Internal to analytics.core.intent_impl.detection
#   Invokes: analytics.core.intent_impl.models.IntentSelectionModel, analytics.core.intent_impl.detection._ensure_required_slots, analytics.core.intent_impl.detection._normalize_metric_slot_statuses, analytics.core.intent_impl.detection._append_missing_followups, +2 more
#   Why: Keeps analytics.core.intent_impl.detection from duplicating llm resolution to runtime behavior across flows.
# Function: resolve_intent_slots_async
#   Role: Handles resolve intent slots async logic for analytics.core.intent_impl.detection.
#   Called from: analytics.flows.planner_executor
#   Invokes: analytics.core.slot_catalog.get_slot_catalog, analytics.core.intent_impl.detection.heuristic_intent, analytics.core.intent_impl.detection._select_candidate_definitions, json.dumps, +2 more
#   Why: Keeps analytics.core.intent_impl.detection from duplicating resolve intent slots async behavior across flows.
# Function: resolve_intent_slots
#   Role: Handles resolve intent slots logic for analytics.core.intent_impl.detection.
#   Called from: Internal to analytics.core.intent_impl.detection
#   Invokes: asyncio.get_running_loop, asyncio.run, analytics.core.intent_impl.detection.resolve_intent_slots_async
#   Why: Keeps analytics.core.intent_impl.detection from duplicating resolve intent slots behavior across flows.
# Function: _llm_to_runtime_intent
#   Role: Handles llm to runtime intent logic for analytics.core.intent_impl.detection.
#   Called from: Internal to analytics.core.intent_impl.detection
#   Invokes: analytics.core.intent_impl.models.IntentModel, analytics.core.intent_impl.models.ClarificationSuggestionModel
#   Why: Keeps analytics.core.intent_impl.detection from duplicating llm to runtime intent behavior across flows.
# Function: classify_query_async
#   Role: Async helper used by agents that already run inside an event loop.
#   Called from: analytics.core.intent, analytics.core.intent_impl, analytics.flows.planner_executor
#   Invokes: unified_responses_client.get_unified_client
#   Why: Supports downstream analytics workflows that rely on classify_query_async.
# Function: classify_query
#   Role: Synchronous wrapper for classification.
#   Called from: analytics.core.intent, analytics.core.intent_impl
#   Invokes: asyncio.get_running_loop, asyncio.run, analytics.core.intent_impl.detection.classify_query_async
#   Why: Supports downstream analytics workflows that rely on classify_query.
# Function: detect_intent_fast_async
#   Role: Fast path: heuristic-first, at most one LLM call, low effort by default.
#   Called from: tests.analytics.test_clarify_comparison
#   Invokes: analytics.core.intent_impl.detection.heuristic_intent, analytics.core.intent_impl.normalization.get_default_tickers, analytics.core.intent_impl.detection._llm_to_runtime_intent, analytics.core.intent_impl.detection.post_process_slots, +2 more
#   Why: Supports downstream analytics workflows that rely on detect_intent_fast_async.
# Function: detect_intent_with_clarifications
#   Role: Synchronous helper maintained for legacy pipelines.
#   Called from: analytics.core.intent_impl
#   Invokes: asyncio.get_running_loop, asyncio.run, analytics.core.intent_impl.detection.detect_intent_fast_async
#   Why: Supports downstream analytics workflows that rely on detect_intent_with_clarifications.
# --- End Analytics Function/Class Map ---
"""
Intent Detection Shared Functions

Provides shared intent detection, classification, and slot post-processing for
analytics workflows. Centralises logic so analytics_memory and
analytics_supervisor share a single implementation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence

from unified_responses_client import get_unified_client

from .models import (
    ClarificationSuggestionModel,
    ClarifyRequestModel,
    IntentModel,
    LLMIntentModel,
    OffTopicClassifierSchema,
    IntentResolutionModel,
    IntentSelectionModel,
    SlotStatusModel,
    FollowUpModel,
    LLMIntentResolutionModel,
)
from .normalization import (
    get_default_tickers,
    normalize_granularity,
    normalize_timeframe,
    normalize_metrics,
    timeframe_implies_quarterly,
)
from ..companies import resolve_alias_to_ticker, sanitize_ticker
from ..slot_catalog import get_slot_catalog, IntentSlotDefinition, SlotOption

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Heuristic Fallbacks
# ---------------------------------------------------------------------------

REQUIRES_COMPANY_SLOTS = {
    "market_share_single",
    "margins_vs_peers",
    "margin_growth_vs_peers",
    "operating_leverage_yoy_vs_peers",
    "rnd_intensity_vs_peers",
    "rnd_expense_vs_peers",
}

HEURISTIC_CONFIDENCE_THRESHOLD = 0.70  # Minimum confidence to short-circuit LLM intent lookup

RANKING_PRONOUNS = {"who", "which", "what"}
RANKING_KEYWORDS = {
    "lead",
    "leads",
    "leading",
    "leader",
    "leaders",
    "top",
    "highest",
    "best",
    "rank",
    "ranking",
    "ranks",
    "dominates",
    "dominant",
    "biggest",
}

AVERAGE_CUES = (
    "industry average",
    "industry-average",
    "average",
    "avg",
)

PEER_CUES = (
    "peer",
    "peers",
    "peer group",
    "peer-group",
)


def _is_ranking_query(query: str) -> bool:
    if not query:
        return False
    lowered = query.lower()
    pronoun_hit = any(token in lowered for token in RANKING_PRONOUNS)
    keyword_hit = any(token in lowered for token in RANKING_KEYWORDS)
    if pronoun_hit and keyword_hit:
        return True
    # Fallback: look for explicit "top N" phrases or "leaderboard"
    if keyword_hit and ("top " in lowered or "leaderboard" in lowered):
        return True
    return False


def _build_company_clarification(companies: List[str]) -> ClarificationSuggestionModel:
    return ClarificationSuggestionModel(
        slot="company",
        reason="This analysis requires a specific company to proceed.",
        question="Which company should we analyse?",
        type="single",
        options=list(companies)[:6],
        proposed=None,
        proposed_confidence=0.0,
    )


def heuristic_intent(query: str, configs: Dict[str, Any]) -> IntentModel:
    """Simple keyword-based intent detection used as a lightweight fallback."""

    q = (query or "").lower()
    companies = get_default_tickers(configs)
    detected_companies = detect_companies_from_query(query, configs, resolve_alias_to_ticker)
    if not detected_companies:
        fallback_company = detect_company_from_query(query, configs, resolve_alias_to_ticker)
        if fallback_company:
            detected_companies = [fallback_company]
    primary_company = detected_companies[0] if detected_companies else None

    average_cue_present = any(cue in q for cue in AVERAGE_CUES)
    peers_cue_present = any(cue in q for cue in PEER_CUES)

    intent_key: Optional[str] = None
    reasoning: List[str] = []
    metric_defaults: List[str] = []
    comparison_default: Optional[str] = None

    if "operating leverage" in q:
        intent_key = "operating_leverage_yoy_vs_peers"
        reasoning.append("Detected operating leverage vs peers intent")
        comparison_default = "vs_avg"
        metric_defaults = ["Operating Income", "Revenue"]
    elif ("eps" in q or "earnings per share" in q) and ("yoy" in q or "year over year" in q or "year-over-year" in q) and _is_ranking_query(query):
        intent_key = "eps_yoy_rank_latest"
        reasoning.append("Detected EPS YoY ranking intent")
        comparison_default = "all"
        metric_defaults = ["EPS Basic"]
    elif ("capex intensity" in q) or (("capital" in q and "intensity" in q) or "capital intensive" in q):
        if _is_ranking_query(query) or any(keyword in q for keyword in ("rank", "leader", "top")):
            intent_key = "capex_intensity_latest_rank"
            reasoning.append("Detected CapEx intensity ranking intent")
            comparison_default = "all"
            metric_defaults = ["Capital Expenditures"]
    elif "market share" in q:
        if "all" in q or any(word in q for word in ("every", "each")):
            intent_key = "market_share_all"
            reasoning.append("Detected market share intent for all companies")
            comparison_default = "all"
        else:
            intent_key = "market_share_single"
            reasoning.append("Detected single-company market share intent")
            comparison_default = "single"
        metric_defaults = ["Revenue"]
    elif (
        "revenue" in q
        and any(
            token in q
            for token in (
                "compare",
                "comparison",
                " vs ",
                "versus",
                "between",
                "among",
            )
        )
    ):
        intent_key = "revenue_comparison"
        reasoning.append("Detected revenue comparison intent")
        metric_defaults = ["Revenue"]
        if len(detected_companies) >= 2 or " vs " in q or "versus" in q:
            comparison_default = "all"
    elif "profit" in q or "earnings" in q:
        intent_key = "margins_vs_peers"
        reasoning.append("Detected profit analysis intent")
        if average_cue_present:
            comparison_default = "vs_avg"
        elif peers_cue_present:
            comparison_default = "vs_peers"
    elif "margin" in q:
        if "growth" in q and any(token in q for token in ("vs", "average", "compare")):
            intent_key = "margin_growth_vs_peers"
            reasoning.append("Detected margin growth vs peers intent")
            if average_cue_present:
                comparison_default = "vs_avg"
            elif peers_cue_present:
                comparison_default = "vs_peers"
        else:
            intent_key = "margins_vs_peers"
            reasoning.append("Detected margin comparison intent")
            if average_cue_present:
                comparison_default = "vs_avg"
            elif peers_cue_present:
                comparison_default = "vs_peers"
    elif "growth" in q or "growing" in q:
        growth_vs_avg_cues = ("vs industry", "vs average", "industry average")
        if any(phrase in q for phrase in (*growth_vs_avg_cues, "vs peers")):
            intent_key = "revenue_growth_vs_avg"
            reasoning.append("Detected revenue growth vs average intent")
            if comparison_default is None:
                if any(cue in q for cue in growth_vs_avg_cues) or (average_cue_present and "peer" not in q):
                    comparison_default = "vs_avg"
        else:
            intent_key = "revenue_growth_analysis"
            reasoning.append("Detected revenue growth intent")
    elif any(token in q for token in ("r&d", "rnd", "research and development")):
        if any(word in q for word in ("highest", "top", "leading", "leader", "largest", "biggest", "most", "rank", "dominant")):
            intent_key = "rnd_top_spender"
            reasoning.append("Detected top R&D spender intent")
        elif "expense" in q or "spending" in q:
            intent_key = "rnd_expense_vs_peers"
            reasoning.append("Detected R&D expense vs peers intent")
            metric_defaults = ["R&D Expense"]
            if comparison_default is None:
                if average_cue_present:
                    comparison_default = "vs_avg"
                elif peers_cue_present:
                    comparison_default = "vs_peers"
        else:
            intent_key = "rnd_intensity_vs_peers"
            reasoning.append("Detected R&D intensity vs peers intent")
            metric_defaults = ["R&D Expense", "Revenue"]

    timeframe_hint = normalize_timeframe(None, query, configs, apply_defaults=False, origin="query")
    slots: Dict[str, Any] = {
        "tickers": detected_companies or companies,
        "granularity": normalize_granularity(query),
    }
    if timeframe_hint:
        slots["timeframe"] = timeframe_hint
    if detected_companies:
        slots["company_candidates"] = detected_companies
    if primary_company:
        slots["company"] = primary_company
    elif intent_key in REQUIRES_COMPANY_SLOTS:
        reasoning.append("Company not detected in query")

    if comparison_default and "comparison" not in slots:
        slots["comparison"] = comparison_default

    if len(detected_companies) >= 2:
        slots["comparison"] = slots.get("comparison") or "all"
        slots["tickers"] = detected_companies

    if metric_defaults and not slots.get("metrics"):
        slots["metrics"] = metric_defaults
        slots["metric"] = metric_defaults[0]

    slots = post_process_slots(slots, query, configs)
    if not primary_company:
        slots.pop("company", None)

    clarifications: List[ClarificationSuggestionModel] = []
    if intent_key in REQUIRES_COMPANY_SLOTS and not primary_company:
        clarifications.append(_build_company_clarification(companies))

    if _is_ranking_query(query):
        slots["comparison"] = "all"
        slots["statistic"] = "ranking_latest"
        reasoning.append("Detected ranking-style request; defaulting to peer comparison")
        if not slots.get("metrics"):
            slots["metrics"] = []

    confidence = 0.75 if intent_key else 0.2
    return IntentModel(
        intent_key=intent_key,
        confidence=confidence,
        slots_detected=slots,
        assumptions=[],
        clarifications_suggested=clarifications,
        possible_intents=[],
        intent_reasoning="; ".join(reasoning) or "Heuristic detection could not determine a clear intent",
    )


def _clone_slot_option(option: Optional[SlotOption]) -> SlotOption:
    if not option:
        return SlotOption()
    return SlotOption(
        suggestions=list(option.suggestions),
        presets=list(option.presets),
        allow_custom=option.allow_custom,
        description=option.description,
    )


def _select_candidate_definitions(
    catalog,
    primary_intent: Optional[str],
    *,
    limit: int = 6,
) -> List[IntentSlotDefinition]:
    definitions: List[IntentSlotDefinition] = []

    if primary_intent:
        definition = catalog.get_intent_definition(primary_intent)
        if definition:
            definitions.append(definition)

    for intent_key in catalog.list_intents():
        if primary_intent and intent_key == primary_intent:
            continue
        definition = catalog.get_intent_definition(intent_key)
        if not definition:
            continue
        if any(existing.intent_key == definition.intent_key for existing in definitions):
            continue
        definitions.append(definition)
        if len(definitions) >= limit:
            break

    return definitions


# ---------------------------------------------------------------------------
# Slot Utilities
# ---------------------------------------------------------------------------

def detect_company_from_query(
    query: str,
    configs: Dict[str, Any],
    resolve_alias_func=resolve_alias_to_ticker,
) -> Optional[str]:
    """Detect a company from free-form text using alias and ticker matching."""

    if not query:
        return None

    companies = get_default_tickers(configs)

    if resolve_alias_func:
        for token in re.findall(r"[A-Za-z0-9&\\.']+", query):
            detected = resolve_alias_func(token, configs)
            if detected:
                return detected

    query_lower = query.lower()
    for ticker in companies:
        if ticker.lower() in query_lower:
            return ticker

    return None


_COMPANY_CONNECTOR_TOKENS = {
    "vs",
    "vs.",
    "versus",
    "and",
    "or",
    "&",
    "against",
    "compare",
    "comparing",
}


def detect_companies_from_query(
    query: str,
    configs: Dict[str, Any],
    resolve_alias_func=resolve_alias_to_ticker,
) -> List[str]:
    """Return all distinct company tickers referenced in the query."""

    if not query:
        return []

    tokens = re.findall(r"[A-Za-z0-9&\\.']+", query)
    if not tokens:
        return []

    default_tickers = get_default_tickers(configs)
    default_lookup = {ticker.lower(): ticker for ticker in default_tickers}

    detected: List[str] = []
    for token in tokens:
        normalized = token.strip().lower().strip(".,:;")
        if not normalized or normalized in _COMPANY_CONNECTOR_TOKENS:
            continue

        ticker: Optional[str] = None
        if resolve_alias_func:
            ticker = resolve_alias_func(token, configs)

        if not ticker:
            candidate = token.strip().upper()
            lowered = candidate.lower()
            if lowered in default_lookup:
                ticker = default_lookup[lowered]
            elif candidate in default_tickers:
                ticker = candidate

        if ticker and ticker not in detected:
            detected.append(ticker)

    return detected



def _normalize_company_candidates(values: Any, query: str) -> List[str]:
    """Return upper-cased company symbols ordered by their appearance in the query."""
    if values is None:
        return []
    if isinstance(values, str):
        candidates = [values]
    elif isinstance(values, (list, tuple, set)):
        candidates = list(values)
    else:
        return []
    deduped: List[str] = []
    for item in candidates:
        symbol = str(item).strip().upper()
        if symbol and symbol not in deduped:
            deduped.append(symbol)
    if not query:
        return deduped
    query_lower = query.lower()
    ranked = []
    for idx, symbol in enumerate(deduped):
        position = query_lower.find(symbol.lower())
        if position == -1:
            position = len(query_lower) + idx
        ranked.append((position, idx, symbol))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [symbol for _, _, symbol in ranked]


def post_process_slots(
    slots: Dict[str, Any],
    query: str,
    configs: Dict[str, Any],
    resolve_alias_func=resolve_alias_to_ticker,
) -> Dict[str, Any]:
    """Normalise detected slots using shared heuristics."""

    processed_slots = dict(slots or {})

    company_candidates = _normalize_company_candidates(processed_slots.get("company"), query)
    if not company_candidates and processed_slots.get("tickers"):
        company_candidates = _normalize_company_candidates(processed_slots.get("tickers"), query)

    query_companies = detect_companies_from_query(query, configs, resolve_alias_func)
    for symbol in query_companies:
        if symbol not in company_candidates:
            company_candidates.append(symbol)

    if company_candidates:
        processed_slots["company_candidates"] = company_candidates
        processed_slots["company"] = company_candidates[0]
        processed_slots["tickers"] = company_candidates
    else:
        existing_company = processed_slots.get("company")
        if isinstance(existing_company, str) and existing_company.strip():
            normalized = existing_company.strip().upper()
            processed_slots["company"] = normalized
            processed_slots.setdefault("tickers", [normalized])
            processed_slots.setdefault("company_candidates", [normalized])
        else:
            processed_slots.pop("company", None)

    if not processed_slots.get("company"):
        detected_company = detect_company_from_query(query, configs, resolve_alias_func)
        if detected_company:
            processed_slots["company"] = detected_company
            processed_slots["tickers"] = [detected_company]
            processed_slots.setdefault("company_candidates", [detected_company])
            logger.info("Post-processed company: %s", detected_company)

    raw_tickers = processed_slots.get("tickers")
    if isinstance(raw_tickers, (list, tuple, set)):
        normalized_tickers: List[str] = []
        for value in raw_tickers:
            symbol = str(value).strip().upper()
            if symbol and symbol not in normalized_tickers:
                normalized_tickers.append(symbol)
        if normalized_tickers:
            processed_slots["tickers"] = normalized_tickers
            processed_slots.setdefault("company_candidates", normalized_tickers)
            processed_slots.setdefault("company", normalized_tickers[0])
            if len(normalized_tickers) >= 2 and processed_slots.get("comparison") in (None, "", "single"):
                processed_slots["comparison"] = "all"
        else:
            processed_slots.pop("tickers", None)


    timeframe = normalize_timeframe(
        processed_slots.get("timeframe"),
        query,
        configs,
        apply_defaults=False,
    )
    if timeframe:
        processed_slots["timeframe"] = timeframe
    else:
        processed_slots.pop("timeframe", None)

    metric_candidates: List[str] = []
    if "metric" in processed_slots:
        metric_candidates.extend(normalize_metrics(processed_slots.get("metric"), configs))
    if "metrics" in processed_slots:
        metric_candidates.extend(normalize_metrics(processed_slots.get("metrics"), configs))

    if metric_candidates:
        deduped_metrics: List[str] = []
        seen_metric = set()
        for value in metric_candidates:
            lowered = value.lower()
            if lowered in seen_metric:
                continue
            deduped_metrics.append(value)
            seen_metric.add(lowered)
        processed_slots["metrics"] = deduped_metrics
        processed_slots["metric"] = deduped_metrics[0]
    else:
        processed_slots.pop("metric", None)
        processed_slots.pop("metrics", None)

    granularity_value = normalize_granularity(query, processed_slots.get("granularity"))
    if timeframe_implies_quarterly(timeframe):
        granularity_value = "quarterly"
    processed_slots["granularity"] = granularity_value
    return processed_slots


def cleanup_clarifications_after_company_detection(
    clarifications: List[Dict[str, Any]],
    detected_company: Optional[str],
) -> List[Dict[str, Any]]:
    """Drop redundant clarifications once a company has been inferred."""

    if not detected_company:
        return clarifications

    filtered = [
        c for c in clarifications
        if c.get("slot") not in {"company", "comparison"}
    ]
    logger.info(
        "Post-processed clarifications after company detection: %d remaining",
        len(filtered),
    )
    return filtered


def _ensure_required_slots(
    slots: Dict[str, SlotStatusModel],
    definition: Optional[IntentSlotDefinition],
) -> None:
    if not definition:
        return

    for slot_name in definition.required_slots:
        option = definition.slot_options.get(slot_name) if definition.slot_options else None
        existing = slots.get(slot_name)
        if existing is None:
            opt = _clone_slot_option(option)
            slots[slot_name] = SlotStatusModel(
                status="missing",
                value=None,
                reason="Resolver omitted a required slot",
                suggestions=list(opt.suggestions),
                allow_custom=opt.allow_custom,
            )
            continue

        if not existing.suggestions and option and option.suggestions:
            slots[slot_name] = existing.model_copy(
                update={
                    "suggestions": list(option.suggestions),
                    "allow_custom": existing.allow_custom if existing.allow_custom is not None else option.allow_custom,
                }
            )


def _append_missing_followups(
    slots: Dict[str, SlotStatusModel],
    followups: List[FollowUpModel],
    definition: Optional[IntentSlotDefinition],
) -> None:
    if not definition:
        return

    existing_slots = {followup.slot for followup in followups}
    for slot_name, slot_state in slots.items():
        if slot_state.status != "missing":
            continue
        if _slot_has_value(slot_state.value):
            continue
        if slot_name in existing_slots:
            continue
        option = definition.slot_options.get(slot_name) if definition.slot_options else None
        opt = _clone_slot_option(option)
        prompt = f"Select a value for {slot_name.replace('_', ' ')}"
        followups.append(
            FollowUpModel(
                slot=slot_name,
                prompt=prompt,
                suggestions=list(opt.suggestions),
                allow_custom=opt.allow_custom,
                reason=slot_state.reason or "This slot is required to continue.",
            )
        )


def _slot_has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, (list, tuple, set)):
        return any(_slot_has_value(item) for item in value)
    return True


def _normalize_metric_slot_statuses(slots: Dict[str, SlotStatusModel]) -> None:
    for slot_name in ("metric", "metrics"):
        slot_state = slots.get(slot_name)
        if slot_state is None:
            continue
        if slot_state.status != "missing":
            continue
        if not _slot_has_value(slot_state.value):
            continue
        slots[slot_name] = slot_state.model_copy(update={"status": "defaulted"})


def _fallback_intent_resolution(
    query: str,
    configs: Dict[str, Any],
    *,
    mode: str,
    heuristic: IntentModel,
    catalog,
    candidate_definitions: Sequence[IntentSlotDefinition],
    context_slots: Optional[Dict[str, Any]] = None,
    fallback_reason: Optional[str] = None,
    emit_optional_followups: bool = True,
) -> IntentResolutionModel:
    intent_key = heuristic.intent_key
    if not intent_key and candidate_definitions:
        intent_key = candidate_definitions[0].intent_key

    definition = catalog.get_intent_definition(intent_key) if intent_key else None
    if not definition and candidate_definitions:
        definition = candidate_definitions[0]

    selection = IntentSelectionModel(
        key=intent_key,
        confidence=heuristic.confidence,
        mode=mode,
    )

    slots: Dict[str, SlotStatusModel] = {}
    followups: List[FollowUpModel] = []
    heuristic_slots = heuristic.slots_detected or {}
    merged_slots: Dict[str, Any] = {}
    merged_slots.update(heuristic_slots)
    if context_slots:
        merged_slots.update({k: v for k, v in context_slots.items() if v is not None})

    option_map = definition.slot_options if definition and definition.slot_options else {}

    company_value = merged_slots.get("company")
    resolved_company = None
    if isinstance(company_value, str) and company_value.strip():
        resolved_company = resolve_alias_to_ticker(company_value, configs) or sanitize_ticker(
            company_value,
            (configs.get("companies", {})
             .get("selection_rules", {})
             .get("default_companies", {})
             .get("tickers", [])),
        )
    if not resolved_company:
        resolved_company = detect_company_from_query(query, configs, resolve_alias_to_ticker)

    timeframe_raw = merged_slots.get("timeframe")

    def _normalize_timeframe_value(raw: Any) -> Optional[Dict[str, Any]]:
        if raw is None:
            return None
        if hasattr(raw, "model_dump"):
            raw = raw.model_dump(exclude_none=True)  # type: ignore[attr-defined]
        if isinstance(raw, dict):
            return raw if raw else None
        return normalize_timeframe(
            raw,
            query,
            configs,
            apply_defaults=False,
            origin="context" if context_slots else "heuristic",
        )

    normalized_timeframe = _normalize_timeframe_value(timeframe_raw)

    metrics_source = merged_slots.get("metrics")
    if not metrics_source:
        metrics_source = merged_slots.get("metric")
    normalized_metrics = normalize_metrics(metrics_source, configs)
    if not normalized_metrics and isinstance(metrics_source, str):
        stripped = metrics_source.strip()
        normalized_metrics = [stripped] if stripped else []
    primary_metric = normalized_metrics[0] if normalized_metrics else None

    comparison_value = merged_slots.get("comparison")
    if isinstance(comparison_value, str):
        comparison_value = comparison_value.strip()
    else:
        comparison_value = None
    tickers_hint = merged_slots.get("tickers")
    if (
        not comparison_value
        and isinstance(tickers_hint, (list, tuple, set))
        and len(
            {
                str(value).strip().upper()
                for value in tickers_hint
                if str(value).strip() and str(value).strip().upper() != "ALL"
            }
        )
        >= 2
    ):
        comparison_value = "all"

    resolved_lookup: Dict[str, Any] = dict(merged_slots)
    resolved_lookup["company"] = resolved_company
    if normalized_timeframe:
        resolved_lookup["timeframe"] = normalized_timeframe
    if primary_metric:
        resolved_lookup["metric"] = primary_metric
    if normalized_metrics:
        resolved_lookup["metrics"] = normalized_metrics
    if comparison_value:
        resolved_lookup["comparison"] = comparison_value

    if definition:
        for slot_name in definition.required_slots:
            normalized = slot_name.split(".", 1)[0] if slot_name else slot_name
            option = option_map.get(normalized)
            opt = _clone_slot_option(option)
            value = resolved_lookup.get(normalized)

            if isinstance(value, str) and not value.strip():
                value = None
            if isinstance(value, (list, tuple, set)) and not any(item is not None for item in value):
                value = None
            if isinstance(value, dict) and not value:
                value = None

            if value is not None:
                slots[normalized] = SlotStatusModel(
                    status="filled",
                    value=value,
                    reason=None,
                    suggestions=list(opt.suggestions),
                    allow_custom=opt.allow_custom,
                )
                continue

            slots[normalized] = SlotStatusModel(
                status="missing",
                value=None,
                reason="Required slot missing",
                suggestions=list(opt.suggestions),
                allow_custom=opt.allow_custom,
            )
            followups.append(
                FollowUpModel(
                    slot=normalized,
                    prompt=f"Select a value for {normalized.replace('_', ' ')}",
                    suggestions=list(opt.suggestions),
                    allow_custom=opt.allow_custom,
                    reason="Heuristic fallback requires this slot.",
                )
            )

        optional_hint_slots = {"metric", "metrics", "timeframe", "comparison"}
        for slot_name in definition.optional_slots:
            normalized = slot_name.split(".", 1)[0] if slot_name else slot_name
            if not normalized or normalized in slots or normalized not in optional_hint_slots:
                continue

            option = option_map.get(normalized)
            opt = _clone_slot_option(option)
            value = resolved_lookup.get(normalized)

            if isinstance(value, str) and not value.strip():
                value = None
            if isinstance(value, (list, tuple, set)) and not any(item is not None for item in value):
                value = None
            if isinstance(value, dict) and not value:
                value = None

            if value is not None:
                reason = None
                status = "defaulted"
                if normalized == "timeframe":
                    status = "defaulted"
                    reason = "Using heuristic timeframe default."
                elif normalized in {"metric", "metrics"}:
                    reason = "Using heuristic metric default."
                elif normalized == "comparison":
                    reason = "Using heuristic comparison default."
                slots[normalized] = SlotStatusModel(
                    status="filled" if normalized in definition.required_slots else status,
                    value=value,
                    reason=reason,
                    suggestions=list(opt.suggestions),
                    allow_custom=opt.allow_custom,
                )
                continue

            if not emit_optional_followups:
                continue

            slots[normalized] = SlotStatusModel(
                status="missing",
                value=None,
                reason="Additional context requested to tailor the analysis.",
                suggestions=list(opt.suggestions),
                allow_custom=opt.allow_custom,
            )
            followups.append(
                FollowUpModel(
                    slot=normalized,
                    prompt=f"Select a value for {normalized.replace('_', ' ')}",
                    suggestions=list(opt.suggestions),
                    allow_custom=opt.allow_custom,
                    reason="Additional context requested to tailor the analysis.",
                )
            )
    notes = fallback_reason or "Intent resolver fell back to heuristic due to unavailable LLM client."
    return IntentResolutionModel(
        intent=selection,
        slots=slots,
        followups=followups,
        notes=notes,
    )


def _llm_resolution_to_runtime(
    llm_res: LLMIntentResolutionModel,
    *,
    catalog,
    candidate_definitions: Sequence[IntentSlotDefinition],
    fallback_confidence: float,
    mode: str,
) -> IntentResolutionModel:
    intent_payload = llm_res.intent or IntentSelectionModel()
    intent_key = intent_payload.key

    if not intent_key and candidate_definitions:
        intent_key = candidate_definitions[0].intent_key

    selection = IntentSelectionModel(
        key=intent_key,
        confidence=intent_payload.confidence or fallback_confidence,
        mode=intent_payload.mode or mode,
    )

    definition = catalog.get_intent_definition(selection.key) if selection.key else None
    if not definition and candidate_definitions:
        definition = next((item for item in candidate_definitions if item.intent_key == selection.key), None)

    def _unwrap_slot_value(raw: Any) -> Any:
        if hasattr(raw, "model_dump"):
            return raw.model_dump(exclude_none=True)
        return raw

    slots: Dict[str, SlotStatusModel] = {}
    for slot_name, slot_payload in (llm_res.slots or {}).items():
        slots[slot_name] = SlotStatusModel(
            status=slot_payload.status,
            value=_unwrap_slot_value(slot_payload.value),
            reason=slot_payload.reason,
            suggestions=list(slot_payload.suggestions or []),
            allow_custom=slot_payload.allow_custom,
        )

    _ensure_required_slots(slots, definition)

    followups: List[FollowUpModel] = []
    for followup in llm_res.followups or []:
        option = definition.slot_options.get(followup.slot) if definition and definition.slot_options else None
        suggestions = list(followup.suggestions or [])
        if not suggestions and option and option.suggestions:
            suggestions = list(option.suggestions)
        allow_custom = followup.allow_custom
        if allow_custom is None and option:
            allow_custom = option.allow_custom
        followups.append(
            FollowUpModel(
                slot=followup.slot,
                prompt=followup.prompt,
                suggestions=suggestions,
                allow_custom=True if allow_custom is None else allow_custom,
                reason=followup.reason,
            )
        )

    _normalize_metric_slot_statuses(slots)

    if followups:
        pruned_followups: List[FollowUpModel] = []
        for followup in followups:
            slot_state = slots.get(followup.slot)
            if slot_state and slot_state.status != "missing":
                continue
            pruned_followups.append(followup)
        followups = pruned_followups

    _append_missing_followups(slots, followups, definition)

    return IntentResolutionModel(
        intent=selection,
        slots=slots,
        followups=followups,
        notes=llm_res.notes,
    )


async def resolve_intent_slots_async(
    query: str,
    configs: Dict[str, Any],
    *,
    mode: str = "single_agent",
    context_slots: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    model: str = "gpt-5-mini-2025-08-07",
    reasoning_effort: str = "low",
) -> IntentResolutionModel:
    catalog = get_slot_catalog()
    heuristic = heuristic_intent(query, configs)

    candidate_definitions = _select_candidate_definitions(catalog, heuristic.intent_key)
    if not candidate_definitions:
        candidate_definitions = _select_candidate_definitions(catalog, None)

    heuristic_context = heuristic.slots_detected or {}
    context_defaults = dict(heuristic_context)
    if context_slots:
        context_defaults.update(context_slots)

    definition = catalog.get_intent_definition(heuristic.intent_key) if heuristic.intent_key else None

    merged_slot_view: Dict[str, Any] = dict(heuristic_context)
    if context_slots:
        merged_slot_view.update({k: v for k, v in context_slots.items() if v is not None})

    def _slot_has_value(slot_name: str) -> bool:
        normalized = slot_name.split(".", 1)[0] if slot_name else slot_name
        if not normalized:
            return False
        value = merged_slot_view.get(normalized)
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set)):
            return any(item not in (None, "", []) for item in value)
        if isinstance(value, dict):
            return bool(value)
        return True

    if (
        definition
        and heuristic.intent_key
        and heuristic.confidence >= HEURISTIC_CONFIDENCE_THRESHOLD
        and all(_slot_has_value(slot) for slot in definition.required_slots)
    ):
        logger.info(
            "Heuristic short-circuit satisfied slots for query '%s' (intent=%s)",
            query,
            heuristic.intent_key,
        )
        return _fallback_intent_resolution(
            query,
            configs,
            mode=mode,
            heuristic=heuristic,
            catalog=catalog,
            candidate_definitions=candidate_definitions,
            context_slots=context_slots,
            fallback_reason="Heuristic resolver satisfied required slots; LLM skipped.",
            emit_optional_followups=False,
        )

    payload = {
        "query": query,
        "mode": mode,
        "context_slots": context_defaults,
        "candidate_intents": [definition.to_dict() for definition in candidate_definitions],
        "heuristic": {
            "intent_key": heuristic.intent_key,
            "confidence": heuristic.confidence,
        },
    }

    system_content = (
        "You are an analytics intent resolver. "
        "Select the best matching intent from the provided candidates and specify slot statuses.\n"
        "- Only use the intents listed in candidate_intents.\n"
        "- For each slot, set status to filled, missing, defaulted, or assumed.\n"
        "- When you default a value, explain why in reason and include it in followups if confirmation is helpful.\n"
        "- Emit followups for slots that need user input; include suggestions when available.\n"
        "- Do not invent companies or metrics that are not mentioned or suggested.\n"
        "- Return compact JSON that matches the requested schema."
    )

    user_content = json.dumps(payload, indent=2, default=str)
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]

    try:
        client = get_unified_client()
    except ValueError:
        logger.warning("OpenAI client unavailable for intent slot resolver; falling back to heuristic.")
        return _fallback_intent_resolution(
            query,
            configs,
            mode=mode,
            heuristic=heuristic,
            catalog=catalog,
            candidate_definitions=candidate_definitions,
            context_slots=context_slots,
        )

    if client is None:
        logger.warning("OpenAI client unavailable for intent slot resolver; falling back to heuristic.")
        return _fallback_intent_resolution(
            query,
            configs,
            mode=mode,
            heuristic=heuristic,
            catalog=catalog,
            candidate_definitions=candidate_definitions,
            context_slots=context_slots,
        )

    try:
        llm_res, _ = await client.create_structured(
            response_model=LLMIntentResolutionModel,
            messages=messages,
            model=model,
            reasoning_effort=reasoning_effort,
            session_id=session_id,
        )
    except Exception as exc:  # pragma: no cover - network errors fallback
        logger.error("Unified slot resolver failed; using heuristic fallback: %s", exc)
        return _fallback_intent_resolution(
            query,
            configs,
            mode=mode,
            heuristic=heuristic,
            catalog=catalog,
            candidate_definitions=candidate_definitions,
            context_slots=context_slots,
        )

    return _llm_resolution_to_runtime(
        llm_res,
        catalog=catalog,
        candidate_definitions=candidate_definitions,
        fallback_confidence=heuristic.confidence,
        mode=mode,
    )


def resolve_intent_slots(
    query: str,
    configs: Dict[str, Any],
    *,
    mode: str = "single_agent",
    context_slots: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    model: str = "gpt-5-mini-2025-08-07",
    reasoning_effort: str = "low",
) -> IntentResolutionModel:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            resolve_intent_slots_async(
                query,
                configs,
                mode=mode,
                context_slots=context_slots,
                session_id=session_id,
                model=model,
                reasoning_effort=reasoning_effort,
            )
        )
    else:
        return loop.run_until_complete(
            resolve_intent_slots_async(
                query,
                configs,
                mode=mode,
                context_slots=context_slots,
                session_id=session_id,
                model=model,
                reasoning_effort=reasoning_effort,
            )
        )


# ---------------------------------------------------------------------------
# LLM-backed Classification / Intent Detection

def _llm_to_runtime_intent(llm_res: LLMIntentModel) -> IntentModel:
    slots_dict: Dict[str, Any] = {}
    try:
        slots_dict = llm_res.slots_detected.model_dump()
    except Exception:  # pragma: no cover - defensive
        slots_dict = {}

    clarifications = []
    for suggestion in getattr(llm_res, "clarifications_suggested", []) or []:
        try:
            clarifications.append(
                ClarificationSuggestionModel(
                    slot=suggestion.slot,
                    reason=suggestion.reason,
                    question=suggestion.question,
                    type=suggestion.type,
                    options=suggestion.options,
                    proposed=suggestion.proposed,
                    proposed_confidence=suggestion.proposed_confidence,
                )
            )
        except Exception:  # pragma: no cover - defensive
            continue

    return IntentModel(
        intent_key=llm_res.intent_key,
        confidence=llm_res.confidence,
        slots_detected=slots_dict,
        assumptions=list(getattr(llm_res, "assumptions", []) or []),
        clarifications_suggested=clarifications,
        possible_intents=list(getattr(llm_res, "possible_intents", []) or []),
        intent_reasoning=getattr(llm_res, "intent_reasoning", "") or "",
    )


async def classify_query_async(
    query: str,
    *,
    session_id: Optional[str] = None,
    model: str = "gpt-5-nano-2025-08-07",
    reasoning_effort: str = "low",
) -> OffTopicClassifierSchema:
    """Async helper used by agents that already run inside an event loop."""

    client = get_unified_client()
    messages = [
        {
            "role": "system",
            "content": (
                "You classify user queries to decide if they request financial analytics support.\n"
                "Return JSON following the OffTopicClassifierSchema.\n"
                "- If the user is off-topic, supply a polite_decline_message under 30 words that redirects them to financial analysis.\n"
                "- When possible, include a suggested_rephrase that turns the query into a valid financial analytics request.\n"
                "- Respect prior context when judging follow-up questions."
            ),
        },
        {"role": "user", "content": f"Classify this query: '{query}'"},
    ]

    result, _ = await client.create_structured(
        response_model=OffTopicClassifierSchema,
        messages=messages,
        model=model,
        reasoning_effort=reasoning_effort,
        session_id=session_id,
    )
    return result


def classify_query(
    query: str,
    *,
    session_id: Optional[str] = None,
    model: str = "gpt-5-nano-2025-08-07",
    reasoning_effort: str = "low",
) -> OffTopicClassifierSchema:
    """Synchronous wrapper for classification."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(classify_query_async(
            query,
            session_id=session_id,
            model=model,
            reasoning_effort=reasoning_effort,
        ))
    else:
        return loop.run_until_complete(classify_query_async(
            query,
            session_id=session_id,
            model=model,
            reasoning_effort=reasoning_effort,
        ))


async def detect_intent_fast_async(
    query: str,
    configs: Dict[str, Any],
    *,
    session_id: Optional[str] = None,
    model: str = "gpt-5-mini-2025-08-07",
    reasoning_effort: str = "low",
) -> IntentModel:
    """Fast path: heuristic-first, at most one LLM call, low effort by default."""

    heuristic = heuristic_intent(query, configs)
    if heuristic.intent_key and heuristic.confidence >= HEURISTIC_CONFIDENCE_THRESHOLD:
        logger.info("Heuristic intent satisfied for query '%s'", query)
        return heuristic

    try:
        client = get_unified_client()
    except ValueError:
        logger.warning("OpenAI client unavailable - using heuristic intent detection")
        return heuristic

    if client is None:
        logger.warning("OpenAI client unavailable - using heuristic intent detection")
        return heuristic

    intents_cfg = list((configs.get("queries", {}) or {}).get("query_patterns", {}).keys())
    companies = get_default_tickers(configs)

    system_content = (
        "You are an analytics intent classifier. Return JSON that matches the IntentModel schema.\n"
        "- Pick the closest supported intent; never reply with unknown.\n"
        "- Fill slots_detected with concrete values from the query text.\n"
        "- Only include clarifications_suggested when a required slot is truly missing.\n"
        "- If a company-specific intent lacks a company, add ONE clarification with slot 'company'.\n"
        "- Keep clarification questions short and decisive.\n"
        "- Do not ask for optional context (e.g. timeframe) unless it is explicitly required and missing.\n"
        "- When the user asks who/which/what along with ranking cues (top, lead/leader, highest, best, rank, dominant), set slots_detected.comparison=\"all\", slots_detected.statistic=\"ranking_latest\", and include the default ticker list unless the user specifies a narrower one.\n"
        "Return JSON only."
    )

    user_content = (
        f"Available intents: {intents_cfg}\n"
        f"Companies (tickers/aliases): {companies}\n"
        f"User query: {query}\n\n"
        "Identify the intent and any missing required slots."
    )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]

    try:
        llm_res, _ = await client.create_structured(
            response_model=LLMIntentModel,
            messages=messages,
            model=model,
            reasoning_effort=reasoning_effort,
            session_id=session_id,
        )
    except Exception as exc:
        logger.error("LLM intent detection failed - falling back to heuristic: %s", exc)
        return heuristic

    intent = _llm_to_runtime_intent(llm_res)

    original_company = intent.slots_detected.get("company")
    intent.slots_detected = post_process_slots(intent.slots_detected, query, configs)

    if not original_company and intent.slots_detected.get("company"):
        intent.clarifications_suggested = cleanup_clarifications_after_company_detection(
            [c.model_dump() for c in intent.clarifications_suggested],
            intent.slots_detected["company"],
        )
        intent.clarifications_suggested = [
            ClarificationSuggestionModel(**c) if not isinstance(c, ClarificationSuggestionModel) else c
            for c in intent.clarifications_suggested
        ]

    if intent.slots_detected.get("comparison") and intent.clarifications_suggested:
        intent.clarifications_suggested = [
            suggestion
            for suggestion in intent.clarifications_suggested
            if getattr(suggestion, "slot", None) != "comparison"
        ]

    logger.info(
        "Intent detection succeeded: intent=%s confidence=%.2f company=%s clarifications=%d",
        intent.intent_key,
        intent.confidence,
        intent.slots_detected.get("company"),
        len(intent.clarifications_suggested),
    )
    return intent




def detect_intent_with_clarifications(
    query: str,
    configs: Dict[str, Any],
    *,
    session_id: Optional[str] = None,
    model: str = "gpt-5-mini-2025-08-07",
    reasoning_effort: str = "low",
) -> IntentModel:
    """Synchronous helper maintained for legacy pipelines."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            detect_intent_fast_async(
                query,
                configs,
                session_id=session_id,
                model=model,
                reasoning_effort=reasoning_effort,
            )
        )
    else:
        return loop.run_until_complete(
            detect_intent_fast_async(
                query,
                configs,
                session_id=session_id,
                model=model,
                reasoning_effort=reasoning_effort,
            )
        )


# Backwards-compatible alias
detect_intent_with_clarifications_async = detect_intent_fast_async
