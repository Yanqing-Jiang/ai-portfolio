# --- Analytics Function/Class Map ---
# Class: ResponseSearchDependencies
#   Role: Handles ResponseSearchDependencies logic for analytics.flows.planner_executor.
#   Called from: tests.analytics.test_pipeline_analysis_offtopic, tests.analytics.test_pipeline_classification_intent
#   Collaborators: dataclasses.dataclass
#   Why: Keeps analytics.flows.planner_executor from duplicating ResponseSearchDependencies behavior across flows.
# Function: _generate_chart_design
#   Role: Generate smart chart design metadata for frontend optimization.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.core.margins.detect_margin_choice_from_plan
#   Why: Supports downstream analytics workflows that rely on _generate_chart_design.
# Function: _validate_sql
#   Role: Handles validate sql logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: time.time, analytics.sql.validator.validate_sql
#   Why: Keeps analytics.flows.planner_executor from duplicating validate sql behavior across flows.
# Class: ToolInvocationReceipt
#   Role: Handles ToolInvocationReceipt logic for analytics.flows.planner_executor.
#   Called from: analytics.flows.single_agent_tools, scripts.seed_agentic_staging, tests.analytics.test_session_state_receipts, tests.analytics.test_single_agent_receipts
#   Collaborators: dataclasses.field, analytics.validators.sanitize_for_json
#   Why: Keeps analytics.flows.planner_executor from duplicating ToolInvocationReceipt behavior across flows.
# Class: PlannerRevisionContext
#   Role: Handles PlannerRevisionContext logic for analytics.flows.planner_executor.
#   Called from: tests.analytics.test_session_state_receipts
#   Collaborators: dataclasses.field, analytics.core.lane_refresh.resolve_lane_ttls, copy.deepcopy
#   Why: Keeps analytics.flows.planner_executor from duplicating PlannerRevisionContext behavior across flows.
# Function: _hash_payload
#   Role: Handles hash payload logic for analytics.flows.planner_executor.
#   Called from: analytics.flows.multi_agent, analytics.flows.single_agent_tools
#   Invokes: analytics.validators.sanitize_for_json, hashlib.sha1, json.dumps
#   Why: Keeps analytics.flows.planner_executor from duplicating hash payload behavior across flows.
# Function: _accessory_tool_adapters
#   Role: Return tool adapters that supply market and web lanes.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.flows.tooling.MarketQuestionAdapter, analytics.flows.tooling.StockTrackerAdapter, analytics.flows.tooling.WebRetrieverAdapter
#   Why: Supports downstream analytics workflows that rely on _accessory_tool_adapters.
# Class: PlannerPhaseContext
#   Role: Handles PlannerPhaseContext logic for analytics.flows.planner_executor.
#   Called from: analytics.flows.multi_agent, analytics.flows.pipeline_tools, analytics.flows.planner.analysis_lane, analytics.flows.planner.fanout, +9 more
#   Collaborators: dataclasses.field
#   Why: Keeps analytics.flows.planner_executor from duplicating PlannerPhaseContext behavior across flows.
# Function: _normalize_calendar_filters
#   Role: Handles normalize calendar filters logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: re.sub
#   Why: Keeps analytics.flows.planner_executor from duplicating normalize calendar filters behavior across flows.
# Function: _set_sql_generation_artifact
#   Role: Handles set sql generation artifact logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.artifacts.SQLGenerationArtifact
#   Why: Keeps analytics.flows.planner_executor from duplicating set sql generation artifact behavior across flows.
# Function: _set_sql_execution_artifact
#   Role: Handles set sql execution artifact logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.flows.planner_executor._summarize_sql_rows, analytics.artifacts.SQLExecutionArtifact
#   Why: Keeps analytics.flows.planner_executor from duplicating set sql execution artifact behavior across flows.
# Function: _run_classifier_with_fallback
#   Role: Retries intent classification across primary and secondary providers.
#   Called from: analytics.flows.planner_executor classification stage
#   Invokes: analytics.flows.planner_executor._run_classifier_with_timeout
#   Why: Keeps classification resilient when the primary provider/model fails.
# Function: _summarize_chart_series
#   Role: Handles summarize chart series logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating summarize chart series behavior across flows.
# Function: _get_sql_dataset
#   Role: Handles get sql dataset logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating get sql dataset behavior across flows.
# Function: _extract_tldr
#   Role: Handles extract tldr logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating extract tldr behavior across flows.
# Function: _extract_bullets
#   Role: Handles extract bullets logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating extract bullets behavior across flows.
# Function: _split_line
#   Role: Handles split line logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating split line behavior across flows.
# Function: _normalize_sentence
#   Role: Handles normalize sentence logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: re.sub
#   Why: Keeps analytics.flows.planner_executor from duplicating normalize sentence behavior across flows.
# Function: _collect_sentences
#   Role: Handles collect sentences logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.flows.planner_executor._split_line, analytics.flows.planner_executor._normalize_sentence
#   Why: Keeps analytics.flows.planner_executor from duplicating collect sentences behavior across flows.
# Function: _extract_key_numbers
#   Role: Handles extract key numbers logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.flows.planner_executor._collect_sentences
#   Why: Keeps analytics.flows.planner_executor from duplicating extract key numbers behavior across flows.
# Function: _extract_risk_watch
#   Role: Handles extract risk watch logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.flows.planner_executor._collect_sentences
#   Why: Keeps analytics.flows.planner_executor from duplicating extract risk watch behavior across flows.
# Function: _extract_next_steps
#   Role: Handles extract next steps logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.flows.planner_executor._collect_sentences
#   Why: Keeps analytics.flows.planner_executor from duplicating extract next steps behavior across flows.
# Function: _build_evidence_entries
#   Role: Handles build evidence entries logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating build evidence entries behavior across flows.
# Function: _evaluate_latency_guardrail
#   Role: Handles evaluate latency guardrail logic for analytics.flows.planner_executor.
#   Called from: analytics.flows.multi_agent
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating evaluate latency guardrail behavior across flows.
# Function: _derive_scope_banner
#   Role: Handles derive scope banner logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.flows.planner_executor._get_sql_dataset
#   Why: Keeps analytics.flows.planner_executor from duplicating derive scope banner behavior across flows.
# Function: _set_chart_artifact
#   Role: Handles set chart artifact logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.flows.planner_executor._summarize_chart_series, analytics.flows.planner_executor._derive_scope_banner, analytics.artifacts.ChartArtifact, json.dumps
#   Why: Keeps analytics.flows.planner_executor from duplicating set chart artifact behavior across flows.
# Function: _set_market_artifact
#   Role: Handles set market artifact logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.artifacts.MarketArtifact
#   Why: Keeps analytics.flows.planner_executor from duplicating set market artifact behavior across flows.
# Function: _set_web_artifact
#   Role: Handles set web artifact logic for analytics.flows.planner_executor.
#   Called from: tests.analytics.test_planner_executor_sql
#   Invokes: analytics.artifacts.WebContextArtifact
#   Why: Keeps analytics.flows.planner_executor from duplicating set web artifact behavior across flows.
# Class: _PayloadSearchResultProxy
#   Role: Minimal wrapper so seeded payloads satisfy the ResponseSearchResult interface.
#   Called from: Internal to analytics.flows.planner_executor
#   Collaborators: copy.deepcopy
#   Why: Supports downstream analytics workflows that rely on _PayloadSearchResultProxy.
# Function: _seed_web_search_from_payload
#   Role: Handles seed web search from payload logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.validators.sanitize_for_json, analytics.flows.planner_executor._PayloadSearchResultProxy, analytics.flows.planner_executor._set_web_artifact
#   Why: Keeps analytics.flows.planner_executor from duplicating seed web search from payload behavior across flows.
# Function: _seed_stock_widget_from_payload
#   Role: Handles seed stock widget from payload logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.validators.sanitize_for_json, analytics.flows.planner_executor._set_market_artifact
#   Why: Keeps analytics.flows.planner_executor from duplicating seed stock widget from payload behavior across flows.
# Function: _set_analysis_artifact
#   Role: Handles set analysis artifact logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.flows.planner_executor._build_evidence_entries, analytics.artifacts.AnalysisArtifact
#   Why: Keeps analytics.flows.planner_executor from duplicating set analysis artifact behavior across flows.
# Function: _build_planner_result_payload
#   Role: Handles build planner result payload logic for analytics.flows.planner_executor.
#   Called from: analytics.flows.multi_agent, analytics.flows.single_agent_tools
#   Invokes: analytics.core.types.PlannerResultModel, copy.deepcopy, analytics.flows.planner_executor._evaluate_latency_guardrail, analytics.flows.planner_executor._build_evidence_entries, +2 more
#   Why: Keeps analytics.flows.planner_executor from duplicating build planner result payload behavior across flows.
# Function: _artifacts_from_snapshot
#   Role: Handles artifacts from snapshot logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating artifacts from snapshot behavior across flows.
# Function: _dataset_preview_from_snapshot
#   Role: Handles dataset preview from snapshot logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating dataset preview from snapshot behavior across flows.
# Function: _snapshot_age_seconds_from_snapshot
#   Role: Handles snapshot age seconds from snapshot logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating snapshot age seconds from snapshot behavior across flows.
# Function: _is_snapshot_fresh
#   Role: Handles is snapshot fresh logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.flows.planner_executor._snapshot_age_seconds_from_snapshot
#   Why: Keeps analytics.flows.planner_executor from duplicating is snapshot fresh behavior across flows.
# Function: _clear_tool_state
#   Role: Handles clear tool state logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating clear tool state behavior across flows.
# Function: _reset_revision_accessories
#   Role: Handles reset revision accessories logic for analytics.flows.planner_executor.
#   Called from: analytics.flows.multi_agent, analytics.flows.single_agent_tools
#   Invokes: analytics.flows.planner_executor._clear_tool_state
#   Why: Keeps analytics.flows.planner_executor from duplicating reset revision accessories behavior across flows.
# Function: _build_revision_snapshot_payload
#   Role: Handles build revision snapshot payload logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.validators.sanitize_for_json, analytics.core.revision_snapshot.build_intent_signature, analytics.flows.planner.limit_sample_rows, copy.deepcopy
#   Why: Keeps analytics.flows.planner_executor from duplicating build revision snapshot payload behavior across flows.
# Function: _compose_reused_analysis_payload
#   Role: Handles compose reused analysis payload logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.validators.sanitize_for_json
#   Why: Keeps analytics.flows.planner_executor from duplicating compose reused analysis payload behavior across flows.
# Function: _build_reused_analysis_event
#   Role: Handles build reused analysis event logic for analytics.flows.planner_executor.
#   Called from: analytics.flows.multi_agent, analytics.flows.single_agent_tools, tests.analytics.test_planner_executor_sql
#   Invokes: analytics.flows.planner_executor._compose_reused_analysis_payload
#   Why: Keeps analytics.flows.planner_executor from duplicating build reused analysis event behavior across flows.
# Function: _compose_reused_analysis_payload
#   Role: Handles compose reused analysis payload logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.validators.sanitize_for_json
#   Why: Keeps analytics.flows.planner_executor from duplicating compose reused analysis payload behavior across flows.
# Function: _build_reused_analysis_event
#   Role: Handles build reused analysis event logic for analytics.flows.planner_executor.
#   Called from: analytics.flows.multi_agent, analytics.flows.single_agent_tools, tests.analytics.test_planner_executor_sql
#   Invokes: analytics.flows.planner_executor._compose_reused_analysis_payload
#   Why: Keeps analytics.flows.planner_executor from duplicating build reused analysis event behavior across flows.
# Function: compose_web_ready_payload
#   Role: Handles compose web ready payload logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: copy.deepcopy, analytics.validators.sanitize_for_json
#   Why: Keeps analytics.flows.planner_executor from duplicating compose web ready payload behavior across flows.
# Function: _build_analysis_source_summaries
#   Role: Handles build analysis source summaries logic for analytics.flows.planner_executor.
#   Called from: analytics.flows.single_agent_tools
#   Invokes: analytics.validators.sanitize_for_json, analytics.artifacts.PipelineArtifacts
#   Why: Keeps analytics.flows.planner_executor from duplicating build analysis source summaries behavior across flows.
# Function: _hydrate_context_from_snapshot
#   Role: Handles hydrate context from snapshot logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.core.revision_snapshot.extract_revision_snapshot, analytics.flows.planner_executor._dataset_preview_from_snapshot, copy.deepcopy, types.SimpleNamespace, +2 more
#   Why: Keeps analytics.flows.planner_executor from duplicating hydrate context from snapshot behavior across flows.
# Function: _apply_revision_context_hints
#   Role: Handles apply revision context hints logic for analytics.flows.planner_executor.
#   Called from: analytics.flows.single_agent_tools, tests.analytics.test_session_state_receipts
#   Invokes: copy.deepcopy
#   Why: Keeps analytics.flows.planner_executor from duplicating apply revision context hints behavior across flows.
# Function: _hydrate_revision_payload
#   Role: Rehydrates planner context inputs from cached revision snapshot payloads.
#   Called from: analytics.flows.planner_executor._apply_revision_context_hints, analytics.flows.planner_executor.PlannerPipeline.events
#   Invokes: analytics.core.types.IntentModel, analytics.core.intent_impl.models.IntentResolutionModel, analytics.core.types.ClarifyRequestModel
#   Why: Keeps analytics.flows.planner_executor from duplicating revision payload hydration behavior across flows.
# Class: PlannerPipeline
#   Role: Phase 2 workflow that emits SSE-friendly events for the memory pipeline.
#   Called from: analytics.flows.pipeline_tools, analytics.flows.planner.analysis_lane, analytics.flows.planner.sql_lane, tests.analytics.test_pipeline_analysis_offtopic, +3 more
#   Collaborators: unified_responses_client.get_unified_client, analytics.flows.schedulers.get_mode_config, analytics.flows.hooks.NullFlowHooks, analytics.core.session_state.get_session_state_repository, +2 more
#   Why: Supports downstream analytics workflows that rely on PlannerPipeline.
# Function: _initialize_context
#   Role: Handles initialize context logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: time.time, analytics.core.events.TimedEventEmitter, analytics.flows.planner_executor.PlannerPhaseContext, analytics.flows.planner_executor._artifacts_from_snapshot, +2 more
#   Why: Keeps analytics.flows.planner_executor from duplicating initialize context behavior across flows.
# Function: _classification_phase
#   Role: Handles classification phase logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.artifacts.ClassificationArtifact, analytics.flows.planner_executor._build_planner_result_payload, analytics.core.intent.classify_query_async, time.time
#   Why: Keeps analytics.flows.planner_executor from duplicating classification phase behavior across flows.
# Function: _intent_phase
#   Role: Handles intent phase logic for analytics.flows.planner_executor.
#   Called from: tests.analytics.test_intent_resolution_telemetry
#   Invokes: time.time, analytics.flows.planner.normalize_metric_slots, analytics.flows.planner.build_slot_assumptions, analytics.flows.planner._compose_intent_from_resolution, +2 more
#   Why: Keeps analytics.flows.planner_executor from duplicating intent phase behavior across flows.
# Function: _clarification_phase
#   Role: Handles clarification phase logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.flows.planner.run_clarification_stage
#   Why: Keeps analytics.flows.planner_executor from duplicating clarification phase behavior across flows.
# Function: _plan_phase
#   Role: Handles plan phase logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.core.revision_snapshot.build_intent_signature, analytics.flows.planner_executor._is_snapshot_fresh, analytics.core.intent.intent_to_sql_criteria, time.time, +2 more
#   Why: Keeps analytics.flows.planner_executor from duplicating plan phase behavior across flows.
# Class: PlannerExecutorFlow
#   Role: Backward-compatible wrapper around :class:`PlannerPipeline`.
#   Called from: analytics.flows.instrumentation, analytics.flows.multi_agent, analytics.flows.single_agent_tools, analytics.flows.workflow, +8 more
#   Collaborators: analytics.flows.planner_executor.PlannerPipeline, analytics.flows.schedulers.apply_mode_metadata
#   Why: Supports downstream analytics workflows that rely on PlannerExecutorFlow.
# Function: run_planner_executor
#   Role: Helper to stream planner-executor events without referencing the registry.
#   Called from: analytics.flows.instrumentation, analytics.flows.multi_agent
#   Invokes: analytics.flows.planner_executor.PlannerExecutorFlow
#   Why: Supports downstream analytics workflows that rely on run_planner_executor.
# --- End Analytics Function/Class Map ---
from __future__ import annotations
import json
import hashlib
from typing import (
    AsyncGenerator,
    Dict,
    Any,
    Optional,
    List,
    Sequence,
    Tuple,
    Set,
    Mapping,
    Iterable,
    Callable,
    Awaitable,
    TYPE_CHECKING,
)
from dataclasses import dataclass, field
import asyncio
import contextlib
from asyncio import QueueEmpty, Task
import re
import os
import logging
import time
import uuid
import copy
from datetime import datetime, date, timezone
from types import SimpleNamespace
from analytics.core.types import (
    WorkflowState,
    SQLResultModel,
    ChartSpecModel,
    ValidationError,
    IntentModel,
    QueryPlanModel,
    ClarifyAnswerModel,
    ClarifyRequestModel,
    PlannerResultModel,
)
from analytics.core.context import get_configs
from analytics.core.config_store import get_config_store
from analytics.core.events import EventEmitter, TimedEventEmitter
from analytics.core.session_state import SnapshotRevisionContext
from analytics.core.lane_refresh import resolve_lane_ttls
from analytics.core.revision_snapshot import (
    build_intent_signature,
    extract_revision_snapshot,
    signatures_equal,
)
from analytics.core import telemetry
from analytics.artifacts import (
    ClassificationArtifact as ClassificationArtifactModel,
    ClarificationArtifact,
    IntentArtifact as IntentArtifactModel,
    PipelineArtifacts,
    PlanArtifact,
    SQLExecutionArtifact,
    SQLGenerationArtifact,
    ChartArtifact,
    WebContextArtifact,
    AnalysisArtifact,
    MarketArtifact,
)
from analytics.routing import FollowUpRoute, FOLLOW_UP_BANNERS
# sanitize_for_json no longer used in this module after persistence delegation
from analytics.flows.planner.receipts import ToolInvocationReceipt as _PlannerToolInvocationReceipt
from analytics.flows.planner.context import PlannerPhaseContext, PlannerRevisionContext

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .revision_directive import RevisionDirective
from .hooks import AnalyticsFlowHooks, NullFlowHooks
from .tooling import (
    run_tool_parallelism,
    get_default_tool_adapters,
    MarketQuestionAdapter,
    StockTrackerAdapter,
    WebRetrieverAdapter,
)
from analytics.core.intent import (
    intent_to_sql_criteria,
    detect_intent,
    detect_intent_llm,
    classify_query_async,
    OffTopicClassifierSchema,
    post_process_slots,
)
from analytics.sql.sql_planner import build_query_plan, choose_template
from analytics.sql.executor import execute_sql
from analytics.sql.templates import fetch_templates_for_intent
from analytics.sql.prompt_builder import build_sql_messages, build_sql_retry_messages, extract_sql_from_response
from analytics.agents.schema_clarifier import ClarifierDecision, decide_schema_clarification
from analytics.core.intent_impl.models import IntentResolutionModel, SlotStatusModel, FollowUpModel
from analytics.core.intent_impl.detection import resolve_intent_slots_async
from analytics.core.charting import build_chart_spec, plan_chart_rule_based
from analytics.core.margins import (
    detect_margin_choice_from_metrics,
    detect_margin_choice_from_plan,
)
from .tool_bundle import collect_tool_bundle
from .chart_revision import emit_chart_patch as _chart_revision_emit, emit_analysis_revision as _analysis_revision_emit
from analytics.core.telemetry import analysis_chunk as log_analysis_chunk, intent_resolution as log_intent_resolution
from .schedulers import FlowMode, get_mode_config, apply_mode_metadata
from analytics.tools.registry import SupervisorTools
from .planner import (
    TOOL_QUEUE_SENTINEL,
    ToolParallelRuntime,
    _cached_event,
    _safe_date,
    _safe_year,
    _summarize_sql_rows,
    annotate_revision_event,
    apply_revision_plan,
    build_revision_plan,
    build_revision_request_event,
    build_slot_assumptions,
    collect_tool_deltas_now,
    compose_chart_ready_payload,
    compose_sql_ready_payload,
    compose_stock_ready_payload,
    compose_web_ready_payload,
    derive_accessory_events,
    derive_revision_targets,
    drain_tool_state_async,
    ensure_analysis_dependencies,
    ensure_tool_receipt,
    hash_payload,
    limit_sample_rows,
    maybe_emit_fresh_lane_event,
    normalize_metric_slots,
    normalize_revision_targets,
    run_analysis_stage,
    run_chart_stage,
    run_chart_pipeline_stage,
    run_clarification_stage,
    run_classification_stage,
    run_sql_pipeline_stage,
    run_intent_stage,
    run_sql_stage,
    start_tool_parallelism,
    stream_analysis_lane,
    stream_chart_lane,
    stream_sql_lane,
    _apply_plan_metric_defaults,
    _apply_plan_timeframe_defaults,
    _build_schema_clarifier_request,
    _clarify_request_to_followup,
    _compose_intent_from_resolution,
    _filter_answered_requests,
    _followup_to_clarify_request,
    _refresh_followups,
    _request_allows_custom,
    _upsert_slot_status,
    _auto_fill_missing_slots,
    SCHEMA_CLARIFIER_ENABLED,
    _normalize_calendar_filters,
    _validate_sql,
    _set_sql_generation_artifact,
    _set_sql_execution_artifact,
    # Text extraction helpers (moved to stage_helpers.py)
    _extract_tldr,
    _extract_bullets,
    _split_line,
    _normalize_sentence,
    _collect_sentences,
    _extract_key_numbers,
    _extract_risk_watch,
    _extract_next_steps,
    _evaluate_latency_guardrail,
    _build_evidence_entries,
    # Snapshot helpers (moved to stage_helpers.py)
    SNAPSHOT_MAX_AGE_SECONDS,
    _artifacts_from_snapshot,
    _dataset_preview_from_snapshot,
    _snapshot_age_seconds_from_snapshot,
    _is_snapshot_fresh,
    _clear_tool_state,
    _reset_revision_accessories,
    _build_revision_snapshot_payload,
    _hydrate_context_from_snapshot as _stage_hydrate_context_from_snapshot,
    _apply_revision_context_hints as _stage_apply_revision_context_hints,
    _hydrate_revision_payload as _stage_hydrate_revision_payload,
    _generate_chart_design as _stage_generate_chart_design,
    _summarize_chart_series as _stage_summarize_chart_series,
    _get_sql_dataset as _stage_get_sql_dataset,
    _derive_scope_banner as _stage_derive_scope_banner,
    _set_chart_artifact as _stage_set_chart_artifact,
    _set_analysis_artifact as _stage_set_analysis_artifact,
    _compose_reused_analysis_payload as _stage_compose_reused_analysis_payload,
    _build_reused_analysis_event as _stage_build_reused_analysis_event,
    _build_analysis_source_summaries as _stage_build_analysis_source_summaries,
    _accessory_tool_adapters as _stage_accessory_tool_adapters,
    _PayloadSearchResultProxy as _stage_PayloadSearchResultProxy,
    _set_market_artifact as _stage_set_market_artifact,
    _set_web_artifact as _stage_set_web_artifact,
    _seed_web_search_from_payload as _stage_seed_web_search_from_payload,
    _seed_stock_widget_from_payload as _stage_seed_stock_widget_from_payload,
    _build_planner_result_payload,
)
from .planner import compose_web_ready_payload
from .planner.session_persistence import persist_session_state
from .pipeline_orchestrator import build_pipeline_lane_executors
from analytics.services.response_search import (
    ResponseSearchError,
    perform_response_search,
    has_search_api_key,
    generate_search_topic,
)
from analytics.core.analysis import stream_insights_llm

@dataclass(frozen=True)
class ResponseSearchDependencies:
    has_api_key: Callable[[], bool]
    generate_topic: Callable[..., Awaitable[Optional[str]]]
    perform_search: Callable[..., Awaitable[Any]]


DEFAULT_RESPONSE_SEARCH = ResponseSearchDependencies(
    has_api_key=has_search_api_key,
    generate_topic=generate_search_topic,
    perform_search=perform_response_search,
)
from unified_responses_client import get_unified_client
CONFIGS = get_configs()
CONFIG_STORE = get_config_store()
SUPERVISOR_TOOLS = SupervisorTools()
logger = logging.getLogger(__name__)

_INTENT_LANE_HINTS: Dict[str, Tuple[str, ...]] = {
    "market_share": ("sql", "chart", "analysis"),
    "ranking": ("sql", "chart", "analysis"),
    "trend": ("sql", "chart", "analysis"),
    "market_analysis": ("stock", "analysis"),
    "market_recap": ("stock", "analysis"),
    "market_update": ("stock", "analysis"),
    "news": ("web", "analysis"),
    "headline": ("web", "analysis"),
    "press": ("web", "analysis"),
    "insight": ("analysis",),
    "summary": ("analysis",),
    "comparison": ("sql", "analysis"),
}

_TOOL_QUEUE_SENTINEL = TOOL_QUEUE_SENTINEL

# Use the shared receipt class from planner.receipts to keep schema in one place.
ToolInvocationReceipt = _PlannerToolInvocationReceipt


_hash_payload = hash_payload

# Delegate helpers directly to staged implementations to keep this facade thin.
_accessory_tool_adapters = _stage_accessory_tool_adapters
_summarize_chart_series = _stage_summarize_chart_series
_get_sql_dataset = _stage_get_sql_dataset
_derive_scope_banner = _stage_derive_scope_banner
_set_chart_artifact = _stage_set_chart_artifact
_set_market_artifact = _stage_set_market_artifact
_set_web_artifact = _stage_set_web_artifact
_PayloadSearchResultProxy = _stage_PayloadSearchResultProxy
_seed_web_search_from_payload = _stage_seed_web_search_from_payload
_seed_stock_widget_from_payload = _stage_seed_stock_widget_from_payload
_set_analysis_artifact = _stage_set_analysis_artifact

FRESH_RUN_REASONING_EFFORT = "minimal"


# _artifacts_from_snapshot, _dataset_preview_from_snapshot, _snapshot_age_seconds_from_snapshot,
# _is_snapshot_fresh moved to planner/stage_helpers.py (P0.3 decomposition)


_compose_reused_analysis_payload = _stage_compose_reused_analysis_payload
_build_reused_analysis_event = _stage_build_reused_analysis_event


_build_analysis_source_summaries = _stage_build_analysis_source_summaries
_hydrate_context_from_snapshot = _stage_hydrate_context_from_snapshot
_apply_revision_context_hints = _stage_apply_revision_context_hints
_hydrate_revision_payload = _stage_hydrate_revision_payload

class PlannerPipeline:
    """Phase 2 workflow that emits SSE-friendly events for the memory pipeline."""

    def __init__(
        self,
        *,
        flow_mode: FlowMode = FlowMode.DIRECT,
        parallelism_enabled: Optional[bool] = None,
        response_search: Optional[ResponseSearchDependencies] = None,
    ) -> None:
        self.unified_client = get_unified_client()
        self.config_store = CONFIG_STORE
        self.flow_label = "planner-executor"
        self.flow_mode = flow_mode
        self.response_search = response_search or DEFAULT_RESPONSE_SEARCH
        self.follow_up_route = FollowUpRoute.FULL_PIPELINE
        self._prefetched_snapshot: Optional[SessionStateSnapshot] = None
        mode_config = get_mode_config(flow_mode)
        # Tool fan-out defaults to the scheduler mode unless explicitly overridden.
        self.parallelism_enabled = mode_config.parallelism_enabled if parallelism_enabled is None else parallelism_enabled
        self.hooks: AnalyticsFlowHooks = NullFlowHooks()
        self._latest_artifacts: Optional[PipelineArtifacts] = None
        self.revision_targets: Set[str] = set()
        self.revision_hint_active: bool = False
        self.revision_directive: Optional["RevisionDirective"] = None
        self.agentic_revision_mode: bool = False
        self._suppress_fresh_pipeline: bool = False
        self._tool_registry: Optional[Any] = None
        self._lane_refresh_required: Dict[str, bool] = {}
        self._analysis_refresh_mode: str = "full"
        self.session_follow_up: bool = False
        self._agent_tool_counters: Dict[str, int] = {}
        self._agent_tool_active_ids: Dict[str, str] = {}

    @property
    def tool_registry(self):
        if self._tool_registry is None:
            from .pipeline_tools import get_planner_tool_registry  # Local import to avoid circular dependency
            self._tool_registry = get_planner_tool_registry()
        return self._tool_registry

    async def _persist_session_state(
        self,
        ctx: PlannerPhaseContext,
        *,
        record_sql: bool = False,
        record_chart: bool = False,
        record_analysis: bool = False,
        record_web: bool = False,
        record_dataset_preview: bool = False,
        tool_bundle: Optional[Dict[str, Any]] = None,
        record_artifacts: bool = True,
    ) -> None:
        session_id = getattr(ctx, "session_id", None)
        if not session_id:
            return
        repository = get_session_state_repository()
        snapshot = await repository.load(session_id)
        if snapshot is None:
            snapshot = SessionStateSnapshot(session_id=session_id)
        updated = False
        sql_artifact = ctx.artifacts.sql_generation if record_sql else None
        if sql_artifact and sql_artifact.sql:
            snapshot.record_outputs(sql=sql_artifact.sql)
            updated = True
        execution_artifact = ctx.artifacts.sql_execution if hasattr(ctx.artifacts, "sql_execution") else None
        row_count_value: Optional[int] = None
        raw_row_count: Any = None
        dataset_receipt_expected = False
        dataset_receipt_written = False
        if execution_artifact:
            preview_rows = getattr(execution_artifact, "dataset_preview", None) or getattr(
                execution_artifact, "sample_rows", None
            )
            raw_row_count = getattr(execution_artifact, "row_count", None)
            row_count_value = normalize_row_count(raw_row_count)
            if row_count_value is not None and row_count_value != raw_row_count:
                try:
                    execution_artifact.row_count = row_count_value
                except Exception:
                    pass
            row_count_provided = False
            if raw_row_count is not None:
                if isinstance(raw_row_count, str):
                    row_count_provided = bool(raw_row_count.strip())
                else:
                    row_count_provided = True
            has_preview_rows = bool(preview_rows and any(preview_rows))
            dataset_receipt_expected = has_preview_rows or row_count_value is not None or row_count_provided
            persist_preview_requested = any(
                [
                    record_dataset_preview,
                    record_artifacts,
                    record_sql,
                    record_web,
                    record_chart,
                    record_analysis,
                    bool(tool_bundle),
                ]
            )
            should_persist_preview = persist_preview_requested and (has_preview_rows or row_count_value is not None)
            if should_persist_preview:
                sanitized_preview = sanitize_for_json(
                    {
                        "rows": preview_rows or [],
                        "row_count": row_count_value,
                    }
                )
                snapshot.record_tool_result("planner_dataset_preview", sanitized_preview)
                dataset_receipt_written = True
                updated = True
        chart_artifact = ctx.artifacts.chart if record_chart else None
        if chart_artifact and chart_artifact.spec:
            snapshot.record_outputs(chart_spec=chart_artifact.spec)
            updated = True
        market_artifact = getattr(ctx.artifacts, "market", None)
        if market_artifact and getattr(market_artifact, "snapshot", None):
            snapshot.record_tool_result(
                "planner_stock_widget",
                sanitize_for_json(market_artifact.snapshot),
            )
            snapshot.touch_lane("market")
            updated = True
        web_artifact = ctx.artifacts.web if record_web else None
        if web_artifact:
            web_payload = web_artifact.to_dict()
            summary = web_payload.get("summary")
            snippets = web_payload.get("snippets")
            if (isinstance(summary, str) and summary.strip()) or (isinstance(snippets, list) and any(snippets)):
                snapshot.record_tool_result("web_search", sanitize_for_json(web_payload))
                updated = True
        analysis_artifact = ctx.artifacts.analysis if record_analysis else None
        if analysis_artifact and analysis_artifact.analysis_text:
            snapshot.record_outputs(analysis=analysis_artifact.analysis_text)
            updated = True
        if tool_bundle:
            sanitized_bundle = sanitize_for_json(tool_bundle)
            snapshot.record_tool_result("planner_bundle", sanitized_bundle)
            if isinstance(tool_bundle, Mapping):
                if tool_bundle.get("web_context"):
                    snapshot.touch_lane("web")
                if tool_bundle.get("stock_widget"):
                    snapshot.touch_lane("market")
            updated = True
        if record_artifacts:
            artifacts_payload = ctx.artifacts.to_dict()
            if artifacts_payload:
                snapshot.record_artifacts(artifacts_payload)
                if isinstance(artifacts_payload, Mapping):
                    web_payload = artifacts_payload.get("web")
                    if (
                        web_payload
                        and not record_web
                        and isinstance(web_payload, Mapping)
                        and (
                            (isinstance(web_payload.get("summary"), str) and web_payload.get("summary").strip())
                            or (
                                isinstance(web_payload.get("snippets"), list)
                                and any(web_payload.get("snippets"))
                            )
                        )
                    ):
                        snapshot.record_tool_result("web_search", sanitize_for_json(web_payload))
                        updated = True
                    if artifacts_payload.get("web"):
                        snapshot.touch_lane("web")
                    analysis_payload = artifacts_payload.get("analysis")
                    if isinstance(analysis_payload, Mapping) and analysis_payload.get("web_context"):
                        snapshot.touch_lane("web")
                    market_payload = artifacts_payload.get("market")
                    if isinstance(market_payload, Mapping) and market_payload.get("snapshot"):
                        snapshot.touch_lane("market")
                updated = True
        revision_payload = _build_revision_snapshot_payload(ctx)
        if revision_payload:
            snapshot.record_revision_snapshot(revision_payload)
            ctx.revision_snapshot = revision_payload
            updated = True
        planner_meta = snapshot.tool_cache.setdefault("planner_metadata", {})
        route_value = getattr(ctx, "follow_up_route", FollowUpRoute.FULL_PIPELINE).value
        if planner_meta.get("follow_up_route") != route_value:
            planner_meta["follow_up_route"] = route_value
            snapshot.tool_cache["planner_metadata"] = planner_meta
            updated = True
        clar_answers = getattr(ctx, "clarification_answers", None)
        if clar_answers:
            cleaned_answers: List[Mapping[str, Any]] = [
                ans for ans in clar_answers if isinstance(ans, Mapping)
            ]
            if cleaned_answers:
                try:
                    answers_payload = sanitize_for_json(list(cleaned_answers))
                except Exception:
                    answers_payload = list(cleaned_answers)
                snapshot.agents_clarifications = (
                    answers_payload if isinstance(answers_payload, list) else list(cleaned_answers)
                )
                snapshot.routing["clarifications_needed"] = False
                updated = True
        clar_needed_flag = getattr(ctx, "clarifications_needed", None)
        if clar_needed_flag is not None:
            snapshot.routing["clarifications_needed"] = bool(clar_needed_flag)
            updated = True
        receipts = getattr(ctx, "tool_receipts", None)
        if receipts:
            for tool_name, receipt in receipts.items():
                if isinstance(receipt, ToolInvocationReceipt):
                    snapshot.record_tool_receipt(tool_name, receipt.to_dict())
                elif isinstance(receipt, dict):
                    snapshot.record_tool_receipt(tool_name, sanitize_for_json(receipt))
            updated = True
        reasoning_entries = getattr(ctx, "revision_reasoning", None) or {}
        if reasoning_entries:
            for key, details in reasoning_entries.items():
                if not isinstance(details, Mapping):
                    continue
                summary = details.get("summary")
                if not summary:
                    continue
                lane = details.get("lane")
                metadata = details.get("metadata") if isinstance(details.get("metadata"), Mapping) else None
                snapshot.record_agent_reasoning(key, summary, lane=lane, metadata=metadata)
            updated = True
        if updated:
            await repository.save(snapshot)
        lane_receipts_cache = {}
        if isinstance(snapshot.tool_cache, dict):
            lane_receipts_cache = snapshot.tool_cache.get("analysis_lane_receipts") or {}
        dataset_receipt_present = (
            isinstance(lane_receipts_cache, dict) and lane_receipts_cache.get("dataset_preview") is not None
        )
        if dataset_receipt_expected and not (dataset_receipt_written or dataset_receipt_present):
            telemetry.analysis_lane_missing_artifact(
                session_id=session_id,
                lane="sql",
                component="dataset_preview",
                reason="receipt_missing",
                metadata={
                    "row_count": row_count_value,
                    "raw_row_count": raw_row_count,
                    "record_dataset_preview": record_dataset_preview,
                    "record_sql": record_sql,
                    "record_artifacts": record_artifacts,
                },
            )

    async def initialize_context(self, query: str, session_id: Optional[str] = None) -> PlannerPhaseContext:
        return await _initialize_context(self, query, session_id)

    def _capture_artifacts(self, ctx: PlannerPhaseContext) -> None:
        self._latest_artifacts = ctx.artifacts

    def latest_artifacts(self) -> Optional[PipelineArtifacts]:
        return self._latest_artifacts

    def prime_with_snapshot(self, snapshot: Optional[SessionStateSnapshot]) -> None:
        self._prefetched_snapshot = snapshot

    def set_follow_up_route(self, route: FollowUpRoute) -> None:
        self.follow_up_route = route

    def set_session_follow_up(self, follow_up: bool) -> None:
        self.session_follow_up = bool(follow_up)

    def set_revision_targets(self, targets: Iterable[str]) -> None:
        normalized = normalize_revision_targets(targets)
        if not normalized:
            self.revision_targets = set()
            self.revision_id = None
            self.revision_hint_active = False
            return
        self.revision_targets = normalized
        self.revision_hint_active = True

    def set_revision_directive(self, directive: Optional["RevisionDirective"]) -> None:
        """Attach a revision directive and seed explicit targets.

        If the directive provides lane targets (e.g., {"analysis", "web"} or
        {"chart"}), record them as `revision_targets` so the revision plan can
        skip unrelated lanes (avoiding unnecessary fresh SQL runs). Also surface
        agentic mode on the pipeline for downstream hooks.
        """
        self.revision_directive = directive
        if directive is not None:
            try:
                targets_iter = getattr(directive, "targets", None) or []
                normalized = {
                    str(t).strip().lower()
                    for t in targets_iter
                    if t is not None and str(t).strip()
                }
                if normalized:
                    self.revision_targets = normalized
                    self.revision_hint_active = True
            except Exception:
                # Defensive: never break flow due to directive parsing
                pass
            self.agentic_revision_mode = bool(getattr(directive, "agentic", False))
        self.agentic_revision_mode = bool(directive.agentic if directive else False)
    def set_lane_refresh_requirements(self, requirements: Optional[Mapping[str, Any]]) -> None:
        normalized: Dict[str, bool] = {}
        if requirements:
            for lane, required in requirements.items():
                if lane is None:
                    continue
                key = str(lane).strip().lower()
                if not key:
                    continue
                normalized[key] = bool(required)
        self._lane_refresh_required = normalized

    def set_analysis_refresh_mode(self, mode: Optional[str]) -> None:
        normalized = "full"
        if isinstance(mode, str):
            candidate = mode.strip().lower()
            if candidate in {"light", "full"}:
                normalized = candidate
        self._analysis_refresh_mode = normalized

    def suppress_fresh_pipeline_events(self) -> None:
        self._suppress_fresh_pipeline = True

    @staticmethod
    def _lane_for_tool_name(tool_name: str) -> Optional[str]:
        normalized = tool_name.strip().lower()
        if not normalized:
            return None
        if normalized.startswith("web_retriever"):
            return "web"
        if normalized == "stock_tracker" or normalized.startswith("market_question"):
            return "market"
        return None

    def _agent_tool_lane(self, tool_name: str, data: Mapping[str, Any]) -> Optional[str]:
        lane_value = data.get("lane")
        if isinstance(lane_value, str) and lane_value.strip():
            return lane_value.strip().lower()
        return self._lane_for_tool_name(tool_name)

    def _build_agent_tool_event_from_payload(
        self,
        ctx: PlannerPhaseContext,
        event: Mapping[str, Any],
        *,
        status: str,
    ) -> Optional[Dict[str, Any]]:
        if not getattr(ctx, "agentic_revision_mode", False):
            return None
        if not isinstance(event, Mapping):
            return None
        data = event.get("data") or {}
        raw_tool = data.get("tool") or data.get("name")
        tool_name = str(raw_tool or "").strip()
        if not tool_name:
            return None
        canonical_tool = tool_name.lower()
        lane = self._agent_tool_lane(canonical_tool, data)
        call_id = self._agent_tool_active_ids.get(canonical_tool)
        if status == "start" or call_id is None:
            counter = self._agent_tool_counters.get(canonical_tool, 0) + 1
            self._agent_tool_counters[canonical_tool] = counter
            call_id = f"{canonical_tool}-{counter}"
            self._agent_tool_active_ids[canonical_tool] = call_id
        if status == "completed":
            self._agent_tool_active_ids.pop(canonical_tool, None)
        attempt = data.get("attempt")
        metadata = data.get("metadata")
        arguments = data.get("arguments")
        payload = data.get("payload")
        reused_flag = data.get("reused")
        parallel_group = data.get("parallel_group")
        elapsed_ms = data.get("elapsed_ms")
        summary = data.get("summary")
        error_detail = data.get("error")
        guardrail_metadata = (
            data.get("latency_guardrail")
            or data.get("guardrail")
            or (metadata.get("latency_guardrail") if isinstance(metadata, Mapping) else None)
            or (metadata.get("guardrail") if isinstance(metadata, Mapping) else None)
        )
        event_payload: Dict[str, Any] = {
            "tool_call": {
                "id": call_id,
                "name": tool_name,
                "lane": lane,
                "status": status,
                "sequence_number": self._agent_tool_counters.get(canonical_tool, 0),
            },
            "tool": tool_name,
            "lane": lane,
            "status": status,
            "ts": datetime.utcnow().isoformat(),
            "session_id": ctx.session_id,
            "follow_up_route": ctx.follow_up_route.value,
        }
        if isinstance(parallel_group, str) and parallel_group.strip():
            event_payload["parallel_group"] = parallel_group.strip()
        if isinstance(attempt, int):
            event_payload["attempt"] = attempt
            event_payload["tool_call"]["attempt"] = attempt
        if isinstance(elapsed_ms, (int, float)):
            event_payload["elapsed_ms"] = int(elapsed_ms)
        if summary:
            event_payload["summary"] = str(summary)
        if error_detail:
            event_payload["error"] = str(error_detail)
        if arguments:
            try:
                sanitized_args = sanitize_for_json(arguments)
                event_payload["tool_call"]["arguments"] = sanitized_args
            except Exception:
                event_payload["tool_call"]["arguments"] = sanitize_for_json(str(arguments))
        if metadata:
            try:
                event_payload["details"] = sanitize_for_json(metadata)
            except Exception:
                event_payload["details"] = sanitize_for_json(str(metadata))
        if payload and status == "completed":
            try:
                event_payload["result"] = sanitize_for_json(payload)
            except Exception:
                event_payload["result"] = sanitize_for_json(str(payload))
        if reused_flag is not None:
            event_payload["reused"] = bool(reused_flag)
        if guardrail_metadata:
            sanitized_guardrail = sanitize_for_json(guardrail_metadata)
            event_payload["latency_guardrail"] = sanitized_guardrail
            event_payload["guardrail"] = sanitized_guardrail
        event_name = "agent_tool_call" if status == "start" else "agent_tool_complete"
        self._memoize_agent_reasoning(
            ctx,
            tool_key=canonical_tool,
            lane=lane,
            status=status,
            event_payload=event_payload,
        )
        annotated = apply_mode_metadata({"event": event_name, "data": event_payload}, self.flow_mode)
        return annotated

    def _build_agent_tool_events_from_manifest(
        self,
        ctx: Optional[PlannerPhaseContext],
        event: Mapping[str, Any],
    ) -> List[Dict[str, Any]]:
        if ctx is None or not getattr(ctx, "agentic_revision_mode", False):
            return []
        data = event.get("data") or {}
        manifest_items = data.get("tools") or ()
        if not isinstance(manifest_items, Iterable):
            return []
        default_parallel = str(data.get("parallel_group") or data.get("tool_group") or "tool_fanout")
        agent_events: List[Dict[str, Any]] = []
        for manifest in manifest_items:
            if not isinstance(manifest, Mapping):
                continue
            tool_name = manifest.get("name") or manifest.get("tool")
            if not tool_name:
                continue
            manifest_data: Dict[str, Any] = {
                "tool": tool_name,
                "lane": manifest.get("lane"),
                "metadata": dict(manifest),
                "parallel_group": manifest.get("parallel_group") or default_parallel,
                "arguments": manifest.get("arguments") or manifest.get("inputs"),
                "summary": manifest.get("summary") or manifest.get("display_name"),
            }
            attempt_value = manifest.get("attempt") or data.get("attempt")
            if isinstance(attempt_value, int):
                manifest_data["attempt"] = attempt_value
            synthetic_event = {"event": "tool_parallel_manifest", "data": manifest_data}
            agent_event = self._build_agent_tool_event_from_payload(ctx, synthetic_event, status="start")
            if agent_event:
                agent_events.append(agent_event)
        return agent_events

    @staticmethod
    def _agent_result_preview(result: Any) -> Optional[Any]:
        if result is None:
            return None
        try:
            sanitized = sanitize_for_json(result)
        except Exception:
            sanitized = str(result)
        if isinstance(sanitized, str):
            return sanitized[:200]
        if isinstance(sanitized, (int, float, bool)):
            return sanitized
        if isinstance(sanitized, list):
            if len(sanitized) <= 3:
                return sanitized
            return {"items": sanitized[:3], "truncated": len(sanitized) - 3}
        if isinstance(sanitized, dict):
            preview: Dict[str, Any] = {}
            for idx, (key, value) in enumerate(sanitized.items()):
                if idx >= 3:
                    preview["__truncated__"] = len(sanitized) - 3
                    break
                preview[key] = value
            return preview
        return sanitized

    def _memoize_agent_reasoning(
        self,
        ctx: Optional[PlannerPhaseContext],
        *,
        tool_key: str,
        lane: Optional[str],
        status: str,
        event_payload: Mapping[str, Any],
    ) -> None:
        if ctx is None or not getattr(ctx, "agentic_revision_mode", False):
            return
        normalized_tool = tool_key.strip().lower()
        if not normalized_tool:
            return
        existing = dict(ctx.revision_reasoning.get(normalized_tool, {}))
        summary = event_payload.get("summary")
        if not summary:
            if status == "start":
                summary = f"Running {tool_key}"
            elif not existing.get("summary"):
                summary = f"{status.title()} {tool_key}"
            else:
                summary = existing.get("summary")
        metadata: Dict[str, Any] = dict(existing.get("metadata") or {})
        for key in ("status", "parallel_group", "attempt", "reused", "elapsed_ms"):
            value = event_payload.get(key)
            if value is not None:
                metadata[key] = value
        error_value = event_payload.get("error")
        if error_value:
            metadata["error"] = error_value
        if status == "completed":
            preview = self._agent_result_preview(event_payload.get("result"))
            if preview is not None:
                metadata["result_preview"] = preview
        entry: Dict[str, Any] = {
            "summary": str(summary) if summary else existing.get("summary", f"{status.title()} {tool_key}"),
            "lane": lane or existing.get("lane"),
        }
        if metadata:
            entry["metadata"] = metadata
        ctx.revision_reasoning[normalized_tool] = entry

    def _record_tool_receipt_from_event(
        self,
        ctx: PlannerPhaseContext,
        tool_name: str,
        status: str,
        data: Mapping[str, Any],
    ) -> None:
        receipts = getattr(ctx, "tool_receipts", None)
        if receipts is None:
            receipts = {}
            ctx.tool_receipts = receipts
        lane = data.get("lane")
        if not lane:
            lane = self._lane_for_tool_name(tool_name)
        metadata = dict(data.get("metadata") or {})
        if lane:
            metadata.setdefault("lane", lane)
        parallel_group = data.get("parallel_group")
        if parallel_group:
            metadata.setdefault("parallel_group", parallel_group)
        payload = data.get("payload") or {}
        if isinstance(payload, Mapping):
            question_id = payload.get("question_id")
            if question_id and "question_id" not in metadata:
                metadata["question_id"] = question_id
        arguments_payload = data.get("arguments")
        if arguments_payload is None and isinstance(metadata.get("arguments"), Mapping):
            arguments_payload = metadata.get("arguments")
        argument_digest = digest_tool_payload(arguments_payload)
        normalized_status = status or "unknown"
        if normalized_status in {"complete", "completed", "success"}:
            normalized_status = "completed"
        elif normalized_status == "cached":
            normalized_status = "reused"
        reused_flag = bool(data.get("reused"))
        receipt = receipts.get(tool_name)
        if receipt:
            receipt.status = "reused" if reused_flag else normalized_status
            receipt.reused = reused_flag
            merged_metadata = dict(receipt.metadata or {})
            merged_metadata.update(metadata)
            receipt.metadata = merged_metadata
            receipt.attempts = max(receipt.attempts, 0) + 1
        else:
            fingerprint = {
                "query": getattr(ctx, "query", None),
                "intent": getattr(getattr(ctx, "intent", None), "intent_key", None),
                "metadata": metadata,
                "tool": tool_name,
            }
            receipt = ToolInvocationReceipt(
                tool=tool_name,
                status="reused" if reused_flag else normalized_status,
                attempts=1,
                input_hash=_hash_payload(fingerprint),
                metadata=metadata,
                reused=reused_flag,
            )
        elapsed_ms = data.get("elapsed_ms")
        if isinstance(elapsed_ms, (int, float)):
            receipt.elapsed_ms = int(elapsed_ms)
        error = data.get("error")
        if error:
            receipt.error = str(error)
        output_payload = payload if isinstance(payload, Mapping) else None
        if output_payload:
            receipt.output_hash = _hash_payload(output_payload)
        if argument_digest and not receipt.arguments_digest:
            receipt.arguments_digest = argument_digest
        output_digest = digest_tool_payload(output_payload)
        if output_digest and not receipt.output_digest:
            receipt.output_digest = output_digest
        guardrail_payload = (
            data.get("latency_guardrail")
            or data.get("guardrail")
            or metadata.get("latency_guardrail")
            or metadata.get("guardrail")
        )
        if isinstance(guardrail_payload, Mapping):
            sanitized_guardrail = sanitize_for_json(guardrail_payload)
            metadata.setdefault("guardrail", sanitized_guardrail)
            metadata.setdefault("latency_guardrail", sanitized_guardrail)
            receipt.latency_guardrail = sanitized_guardrail
            receipt.guardrail = sanitized_guardrail
        completed_at = data.get("completed_at") or data.get("ts")
        if completed_at:
            receipt.timestamp = str(completed_at)
        else:
            receipt.timestamp = datetime.utcnow().isoformat()
        receipts[tool_name] = receipt

    def _annotate_revision(self, event: Dict[str, Any], ctx: Optional[PlannerPhaseContext]) -> Dict[str, Any]:
        return annotate_revision_event(event, ctx)

    def _mark_delta_event(self, event: Dict[str, Any], ctx: Optional[PlannerPhaseContext] = None) -> Dict[str, Any]:
        data = event.setdefault("data", {})
        data["delta"] = True
        data.setdefault("parallel_group", "accessory_delta")
        return self._annotate_revision(event, ctx)

    @staticmethod
    def _apply_revision_metadata(
        event: Dict[str, Any],
        *,
        reason: Optional[str],
        source: Optional[str],
    ) -> Dict[str, Any]:
        if not isinstance(event, dict):
            return event
        data = event.setdefault("data", {})
        if reason and not data.get("reason"):
            data["reason"] = reason
        if source and not data.get("source"):
            data["source"] = source
        return event

    def _update_tool_result_cache(self, ctx: PlannerPhaseContext, entries: Sequence[Dict[str, Any]]) -> None:
        if not entries:
            return
        existing_results: List[Dict[str, Any]] = list(getattr(ctx, "tool_parallel_results", []) or [])
        for entry in entries:
            if isinstance(entry, dict):
                existing_results.append(copy.deepcopy(entry))
        if not existing_results:
            return
        dedup: List[Dict[str, Any]] = []
        seen: Set[Tuple[str, str, Optional[str], Optional[str]]] = set()
        for result in reversed(existing_results):
            if not isinstance(result, dict):
                continue
            tool_id = str(result.get("tool") or "").strip().lower()
            event_name = str(result.get("event") or "tool_parallel_result").strip().lower()
            payload_entry = result.get("payload")
            question_id: Optional[str] = None
            lane_id: Optional[str] = None
            if isinstance(payload_entry, Mapping):
                raw_qid = payload_entry.get("question_id") or payload_entry.get("id")
                if isinstance(raw_qid, (str, int)):
                    question_id = str(raw_qid)
                lane_val = payload_entry.get("lane")
                if isinstance(lane_val, str):
                    lane_id = lane_val.strip().lower() or None
            key = (tool_id, event_name, question_id, lane_id)
            if key in seen:
                continue
            seen.add(key)
            dedup.append(result)
        dedup.reverse()
        ctx.tool_parallel_results = dedup[-10:]

    def _ingest_tool_event(self, ctx: PlannerPhaseContext, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        derived: List[Dict[str, Any]] = []
        if not isinstance(event, dict):
            return derived
        if event.get("event") != "tool_parallel_result":
            return derived
        data = event.get("data") or {}
        tool_name = str(data.get("tool") or "").strip().lower()
        status = str(data.get("status") or "").strip().lower()
        payload = data.get("payload") or {}
        if tool_name.startswith("web_retriever") and status in {"completed", "complete", "success"}:
            if isinstance(payload, dict) and payload.get("ready"):
                _seed_web_search_from_payload(ctx, payload)
        elif (
            tool_name == "stock_tracker"
            or tool_name.startswith("market_question")
        ) and status in {"completed", "complete", "success"}:
            if isinstance(payload, dict):
                _seed_stock_widget_from_payload(ctx, payload)
        if tool_name in {"web_retriever", "stock_tracker"} or tool_name.startswith("market_question"):
            self._record_tool_receipt_from_event(ctx, tool_name, status, data)
        flow_mode_value = getattr(self, "flow_mode", FlowMode.DIRECT).value
        derived.extend(
            derive_accessory_events(
                ctx,
                tool_name=tool_name,
                status=status,
                data=data,
                flow_mode_value=flow_mode_value,
                mark_delta_event=self._mark_delta_event,
                compose_stock_ready_payload=compose_stock_ready_payload,
                compose_web_ready_payload=compose_web_ready_payload,
            )
        )
        if tool_name.startswith("web_retriever") and status in {"completed", "complete", "success"}:
            has_web_ready = any(evt.get("event") == "web_ready" for evt in derived if isinstance(evt, dict))
            if not has_web_ready and isinstance(payload, Mapping) and payload.get("ready"):
                fallback_payload = dict(payload)
                fallback_payload.setdefault("reused", bool(payload.get("from_cache") or data.get("reused")))
                fallback_payload.setdefault("schedule_stage", data.get("schedule_stage") or "hedged_accessories")
                fallback_payload.setdefault("parallel_group", data.get("parallel_group") or "tool_fanout")
                fallback_payload.setdefault("lane", "web")
                fallback_payload.setdefault("flow_mode", flow_mode_value)
                fallback_payload.setdefault("ts", data.get("completed_at") or data.get("ts") or datetime.utcnow().isoformat())
                derived.append(
                    self._mark_delta_event(
                        {
                            "event": "web_ready",
                            "data": fallback_payload,
                        },
                        ctx,
                    )
                )
                ctx.web_ready_emitted = True  # type: ignore[attr-defined]
        lane_for_fresh: Optional[str] = None
        if tool_name.startswith("web_retriever"):
            lane_for_fresh = "web"
        elif tool_name == "stock_tracker" or tool_name.startswith("market_question"):
            lane_for_fresh = "stock"
        if lane_for_fresh:
            if status in {"completed", "complete", "success"}:
                marker = maybe_emit_fresh_lane_event(self, ctx, lane_for_fresh, "completed")
            elif status in {"failed", "error", "cancelled"}:
                marker = maybe_emit_fresh_lane_event(self, ctx, lane_for_fresh, "failed")
            else:
                marker = None
            if marker:
                derived.append(marker)
        cache_entries: List[Dict[str, Any]] = []
        normalized_result = sanitize_for_json(dict(data))
        if isinstance(normalized_result, dict):
            normalized_result.setdefault("tool", tool_name)
            normalized_result.setdefault("status", status)
            normalized_result.setdefault("event", "tool_parallel_result")
            cache_entries.append(normalized_result)
        for derived_event in derived:
            if not isinstance(derived_event, dict):
                continue
            event_name = str(derived_event.get("event") or "").strip().lower()
            if event_name not in {"stock_ready", "web_ready"}:
                continue
            payload_mapping = derived_event.get("data")
            normalized_payload: Dict[str, Any] = {}
            if isinstance(payload_mapping, Mapping):
                normalized_payload = sanitize_for_json(dict(payload_mapping)) or {}
                if not isinstance(normalized_payload, dict):
                    normalized_payload = dict(payload_mapping)
            cache_entries.append(
                {
                    "tool": tool_name or derived_event.get("event"),
                    "status": "ready",
                    "event": derived_event.get("event"),
                    "payload": normalized_payload,
                    "lane": normalized_payload.get("lane") if isinstance(normalized_payload, dict) else None,
                    "reused": normalized_payload.get("reused") if isinstance(normalized_payload, dict) else None,
                    "source": "accessory_delta",
                }
            )
        if cache_entries:
            self._update_tool_result_cache(ctx, cache_entries)
        return derived

    def _start_tool_parallelism(
        self,
        ctx: PlannerPhaseContext,
        *,
        adapters: Optional[Sequence[Any]] = None,
        concurrency_override: Optional[int] = None,
    ) -> ToolParallelRuntime:
        return start_tool_parallelism(
            ctx,
            ingest_tool_event=self._ingest_tool_event,
            adapters=adapters,
            concurrency_override=concurrency_override,
        )

    def _fanout_adapters_for_context(self, ctx: PlannerPhaseContext) -> Tuple[Any, ...]:
        targets = set(ctx.revision_targets or ())
        if not targets:
            return get_default_tool_adapters()
        adapters: List[Any] = []
        if "market" in targets:
            adapters.extend(
                [
                    MarketQuestionAdapter("market_question_a", "Market Research Question A"),
                    MarketQuestionAdapter("market_question_b", "Market Research Question B"),
                ]
            )
        if "stock" in targets or "market" in targets:
            adapters.append(StockTrackerAdapter())
        if "web" in targets or "market" in targets:
            adapters.append(WebRetrieverAdapter())
        if not adapters and "stock" in targets:
            adapters.append(StockTrackerAdapter())
        if not adapters and "web" in targets:
            adapters.append(WebRetrieverAdapter())
        return tuple(adapters)

    async def refresh_accessory_lanes(
        self,
        ctx: PlannerPhaseContext,
        lanes: Sequence[str],
        *,
        reason: Optional[str] = None,
        source: Optional[str] = None,
        lane_reason: Optional[Mapping[str, str]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fan out accessory lanes (web/market) and stream their tool events.
        """
        runtime = self._start_tool_parallelism(ctx, adapters=get_default_tool_adapters())
        start_ts = time.perf_counter()
        lane_reason_lookup = dict(lane_reason or {})
        if not hasattr(ctx, "accessory_stage_ms") or ctx.accessory_stage_ms is None:
            ctx.accessory_stage_ms = {}
        try:
            while True:
                event = await runtime.queue.get()
                if event is _TOOL_QUEUE_SENTINEL:
                    break
                if isinstance(event, dict):
                    data = event.setdefault("data", {})
                    if isinstance(data, dict):
                        lane = data.get("lane")
                        if lane and lane in lane_reason_lookup:
                            data["reason"] = lane_reason_lookup[lane]
                        elif reason is not None:
                            data.setdefault("reason", reason)
                        if source is not None:
                            data.setdefault("source", source)
                        if lane:
                            ctx.accessory_stage_ms[lane] = int((time.perf_counter() - start_ts) * 1000)
                yield event
        finally:
            await runtime.close()

    async def _stream_with_tool_state(
        self,
        stream: AsyncGenerator[Dict[str, Any], None],
        tool_state: Optional[Dict[str, Any]],
        ctx: Optional[PlannerPhaseContext] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if tool_state is None or not tool_state.get("active", False):
            async for event in stream:
                if ctx and getattr(ctx, "cancelled", False):
                    break
                yield self._annotate_revision(event, ctx)
            return

        tool_queue: asyncio.Queue = tool_state["queue"]
        runtime = tool_state.get("runtime")
        multiplex_queue: asyncio.Queue = asyncio.Queue()
        sql_done_token: object = object()
        tool_done_token: object = object()

        def _deactivate_runtime() -> None:
            tool_state["active"] = False
            runtime_obj = tool_state.get("runtime")
            if isinstance(runtime_obj, ToolParallelRuntime):
                runtime_obj.active = False

        async def _pump_sql() -> None:
            done_posted = False
            try:
                async for event in stream:
                    if ctx and getattr(ctx, "cancelled", False):
                        break
                    await multiplex_queue.put(("sql", event))
            except asyncio.CancelledError:
                raise
            finally:
                if not done_posted:
                    await multiplex_queue.put((sql_done_token, None))
                    done_posted = True

        async def _drain_tool_queue() -> None:
            done_posted = False
            try:
                while True:
                    tool_event = await tool_queue.get()
                    if tool_event is _TOOL_QUEUE_SENTINEL:
                        _deactivate_runtime()
                        await multiplex_queue.put((tool_done_token, None))
                        done_posted = True
                        break
                    await multiplex_queue.put(("tool", tool_event))
            except asyncio.CancelledError:
                raise
            finally:
                if not done_posted:
                    _deactivate_runtime()
                    await multiplex_queue.put((tool_done_token, None))

        sql_task = asyncio.create_task(_pump_sql())
        tool_task = asyncio.create_task(_drain_tool_queue())
        sql_complete = False
        tool_complete = False

        try:
            while not (sql_complete and tool_complete):
                source, payload = await multiplex_queue.get()
                if ctx and getattr(ctx, "cancelled", False):
                    break

                if source is sql_done_token:
                    sql_complete = True
                    continue
                if source is tool_done_token:
                    tool_complete = True
                    continue

                if source == "tool":
                    if not getattr(self, "_run_tools_supported", True):
                        continue
                    event_name = str(payload.get("event") or "").strip().lower()
                    if event_name == "tool_parallel_start":
                        start_events = self._build_agent_tool_events_from_manifest(ctx, payload)
                        for agent_event in start_events:
                            yield self._annotate_revision(agent_event, ctx)
                        yield self._mark_delta_event(payload, ctx)
                        continue
                    try:
                        logger.debug(
                            "planner_executor.tool_delta_emitted",
                            extra={
                                "flow_mode": getattr(self, "flow_mode", FlowMode.DIRECT).value,
                                "event": payload.get("event"),
                                "tool": (payload.get("data") or {}).get("tool"),
                            },
                        )
                    except Exception:
                        pass
                    agent_start_event = self._build_agent_tool_event_from_payload(ctx, payload, status="start")
                    if agent_start_event:
                        yield self._annotate_revision(agent_start_event, ctx)
                    yield self._mark_delta_event(payload, ctx)
                    agent_complete_event = self._build_agent_tool_event_from_payload(
                        ctx,
                        payload,
                        status="completed",
                    )
                    if agent_complete_event:
                        yield self._annotate_revision(agent_complete_event, ctx)
                    continue

                if source == "sql":
                    try:
                        logger.debug(
                            "planner_executor.core_event_emitted",
                            extra={
                                "flow_mode": getattr(self, "flow_mode", FlowMode.DIRECT).value,
                                "event": payload.get("event"),
                                "step": payload.get("data", {}).get("step") if isinstance(payload.get("data"), dict) else None,
                            },
                        )
                    except Exception:
                        pass
                    yield self._annotate_revision(payload, ctx)
        finally:
            for task in (sql_task, tool_task):
                task.cancel()
                with contextlib.suppress(Exception):
                    await task

    def _flush_tool_events(self, queue: asyncio.Queue, ctx: Optional[PlannerPhaseContext] = None) -> List[Dict[str, Any]]:
        """Drain any immediately available tool events without blocking."""
        flushed: List[Dict[str, Any]] = []
        sentinel_found = False
        while True:
            try:
                event = queue.get_nowait()
            except QueueEmpty:
                break
            if event is _TOOL_QUEUE_SENTINEL:
                sentinel_found = True
                break
            flushed.append(self._mark_delta_event(event, ctx))
        if sentinel_found:
            queue.put_nowait(_TOOL_QUEUE_SENTINEL)
        return flushed


    async def _emit_post_analysis_accessories(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        mode_config = get_mode_config(ctx.flow_mode)
        if mode_config.accessories_in_critical_path:
            return

        lane_refresh_flags = dict(getattr(ctx, "lane_refresh_required", {}) or {})
        web_refresh_required = bool(lane_refresh_flags.get("web", True))
        market_refresh_required = bool(lane_refresh_flags.get("market", True))

        adapter_lookup = {adapter.name: adapter for adapter in get_default_tool_adapters()}
        if not adapter_lookup:
            if web_refresh_required and ctx.web_search is None and not getattr(ctx, "web_search_seeded", False):
                async for event in self._web_search_phase(ctx):
                    yield self._mark_delta_event(event)
            await self._persist_session_state(ctx, record_artifacts=True, record_web=True)
            return
        if not getattr(self, "_run_tools_supported", True):
            if web_refresh_required and ctx.web_search is None and not getattr(ctx, "web_search_seeded", False):
                async for event in self._web_search_phase(ctx):
                    yield self._mark_delta_event(event)
            await self._persist_session_state(ctx, record_artifacts=True, record_web=True)
            return

        accessory_tools: Set[str] = set()
        if web_refresh_required:
            accessory_tools.add("web_retriever")
        if market_refresh_required:
            accessory_tools.add("stock_tracker")

        existing_results = getattr(ctx, "tool_parallel_results", []) or []
        completed_tools = {result.get("tool") for result in existing_results}
        pending_tools = [tool for tool in accessory_tools if tool not in completed_tools]
        if pending_tools and asyncio.iscoroutinefunction(run_tool_parallelism):
            adapters = [adapter_lookup[name] for name in pending_tools if name in adapter_lookup]
            if adapters:
                async for event in run_tool_parallelism(
                    ctx,
                    adapters=tuple(adapters),
                    concurrency_override=len(adapters),
                ):
                    derived_events = self._ingest_tool_event(ctx, event)
                    yield self._mark_delta_event(event)
                    for derived_event in derived_events:
                        yield derived_event

        if web_refresh_required and ctx.web_search is None and not getattr(ctx, "web_search_seeded", False):
            async for event in self._web_search_phase(ctx):
                yield self._mark_delta_event(event)
        await self._persist_session_state(
            ctx,
            record_artifacts=True,
            record_web=bool(getattr(ctx.artifacts, "web", None)),
        )

    async def refresh_web_lane(
        self,
        ctx: PlannerPhaseContext,
        *,
        reason: Optional[str] = None,
        source: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        refresh_flags = dict(getattr(ctx, "lane_refresh_required", {}) or {})
        force_live = bool(getattr(ctx, "force_revision_refresh", False))
        if refresh_flags.get("web") is False and not force_live:
            setattr(ctx, "reused_web", True)
            refresh_flags["web"] = False
            ctx.lane_refresh_required = refresh_flags
            snapshot = getattr(ctx, "revision_snapshot", None)
            age_seconds = None
            if snapshot is not None and hasattr(snapshot, "lane_age_seconds"):
                try:
                    age_seconds = snapshot.lane_age_seconds("web")
                except Exception:
                    age_seconds = None
            reuse_event = EventEmitter.status("web_refresh", "Web refresh skipped; using cached context.")
            reuse_event.setdefault("data", {}).update(
                {
                    "lane": "web",
                    "revision": True,
                    "phase": "reused",
                    "reused": True,
                    "from_cache": True,
                }
            )
            if age_seconds is not None:
                reuse_event["data"]["age_seconds"] = age_seconds
            yield self._apply_revision_metadata(reuse_event, reason=reason, source=source)

            lane_reuse = self._build_lane_reuse_event(ctx, "web", reason=reason or "cached_web_ready")
            if lane_reuse:
                yield lane_reuse

            web_payload = compose_web_ready_payload(ctx)
            if web_payload:
                web_payload.setdefault("lane", "web")
                web_payload.setdefault("reused", True)
                web_payload.setdefault("from_cache", True)
                ready_event = EventEmitter.status("web_ready", "Web context ready (cache).")
                ready_event["event"] = "web_ready"
                ready_event.setdefault("data", {}).update(web_payload)
                yield self._apply_revision_metadata(self._annotate_revision(ready_event, ctx), reason=reason, source=source)
                setattr(ctx, "web_ready_emitted", True)
            await self._persist_session_state(ctx, record_artifacts=True, record_web=True)
            return

        _reset_revision_accessories(ctx, {"web"})
        adapter_lookup = {adapter.name: adapter for adapter in get_default_tool_adapters()}
        adapter_names = tuple(name for name in ("web_retriever", "web_retriever_cached", "web_retriever_live") if name in adapter_lookup)
        if not adapter_names:
            skip_event = EventEmitter.status("web_refresh", "Web retriever unavailable")
            skip_event.setdefault("data", {})
            skip_event["data"].update({"lane": "web", "revision": True, "phase": "skipped"})
            yield self._apply_revision_metadata(skip_event, reason=reason, source=source)
            return
        adapters = tuple(adapter_lookup[name] for name in adapter_names)
        try:
            async for event in run_tool_parallelism(
                ctx,
                adapters=adapters,
                concurrency_override=len(adapters),
            ):
                derived_events = self._ingest_tool_event(ctx, event)
                base_event = self._apply_revision_metadata(
                    self._mark_delta_event(event, ctx),
                    reason=reason,
                    source=source,
                )
                yield base_event
                for derived_event in derived_events:
                    yield self._apply_revision_metadata(
                        derived_event,
                        reason=reason,
                        source=source,
                    )
        finally:
            await self._persist_session_state(ctx, record_artifacts=True, record_web=True)

    async def refresh_market_lane(
        self,
        ctx: PlannerPhaseContext,
        *,
        reason: Optional[str] = None,
        source: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        refresh_flags = dict(getattr(ctx, "lane_refresh_required", {}) or {})
        force_live = bool(getattr(ctx, "force_revision_refresh", False))
        if refresh_flags.get("market") is False and not force_live:
            setattr(ctx, "reused_stock", True)
            refresh_flags["market"] = False
            ctx.lane_refresh_required = refresh_flags
            snapshot = getattr(ctx, "revision_snapshot", None)
            age_seconds = None
            if snapshot is not None and hasattr(snapshot, "lane_age_seconds"):
                try:
                    age_seconds = snapshot.lane_age_seconds("market")
                except Exception:
                    age_seconds = None
            reuse_event = EventEmitter.status("market_refresh", "Market refresh skipped; using cached snapshot.")
            reuse_event.setdefault("data", {}).update(
                {
                    "lane": "market",
                    "revision": True,
                    "phase": "reused",
                    "reused": True,
                    "from_cache": True,
                }
            )
            if age_seconds is not None:
                reuse_event["data"]["age_seconds"] = age_seconds
            yield self._apply_revision_metadata(reuse_event, reason=reason, source=source)

            lane_reuse = self._build_lane_reuse_event(ctx, "market", reason=reason or "cached_market_ready")
            if lane_reuse:
                yield lane_reuse

            stock_payload = compose_stock_ready_payload(ctx)
            if stock_payload:
                stock_payload.setdefault("lane", "market")
                stock_payload.setdefault("reused", True)
                stock_payload.setdefault("from_cache", True)
                ready_event = EventEmitter.status("stock_ready", "Stock context ready (cache).")
                ready_event["event"] = "stock_ready"
                ready_event.setdefault("data", {}).update(stock_payload)
                yield self._apply_revision_metadata(self._annotate_revision(ready_event, ctx), reason=reason, source=source)
            await self._persist_session_state(ctx, record_artifacts=True)
            return

        _reset_revision_accessories(ctx, {"market"})
        adapter_lookup = {adapter.name: adapter for adapter in get_default_tool_adapters()}
        adapter_names = tuple(
            name for name in ("market_question_a", "market_question_b", "stock_tracker") if name in adapter_lookup
        )
        if not adapter_names:
            skip_event = EventEmitter.status("market_refresh", "Market tools unavailable")
            skip_event.setdefault("data", {})
            skip_event["data"].update({"lane": "market", "revision": True, "phase": "skipped"})
            yield self._apply_revision_metadata(skip_event, reason=reason, source=source)
            return
        adapters = tuple(adapter_lookup[name] for name in adapter_names)
        try:
            async for event in run_tool_parallelism(
                ctx,
                adapters=adapters,
                concurrency_override=len(adapters),
            ):
                derived_events = self._ingest_tool_event(ctx, event)
                base_event = self._apply_revision_metadata(
                    self._mark_delta_event(event, ctx),
                    reason=reason,
                    source=source,
                )
                yield base_event
                for derived_event in derived_events:
                    yield self._apply_revision_metadata(
                        derived_event,
                        reason=reason,
                        source=source,
                    )
        finally:
            await self._persist_session_state(ctx, record_artifacts=True)

    async def emit_chart_patch(
        self,
        *,
        session_id: str,
        patch: Dict[str, Any],
        reason: Optional[str] = None,
        source: Optional[str] = None,
        repository: Optional[Any] = None,
        hooks: Optional[AnalyticsFlowHooks] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        stream = _chart_revision_emit(
            session_id=session_id,
            patch=patch,
            reason=reason,
            source=source,
            repository=repository,
        )
        if hooks is None:
            async for event in stream:
                yield event
            return

        hook_ctx: Dict[str, Any] = {"session_id": session_id}
        try:
            async for start_event in hooks.on_flow_start(hook_ctx):
                yield start_event
            async for event in stream:
                async for pre_event in hooks.before_event(hook_ctx, event):
                    yield pre_event
                yield event
                async for post_event in hooks.after_event(hook_ctx, event):
                    yield post_event
        except BaseException as exc:
            async for end_event in hooks.on_flow_end(hook_ctx, error=exc):
                yield end_event
            raise
        else:
            async for end_event in hooks.on_flow_end(hook_ctx):
                yield end_event


    async def run_classification(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in run_classification_stage(self, ctx):
            yield event

    async def run_intent(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in run_intent_stage(self, ctx):
            yield event

    async def run_clarification(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in run_clarification_stage(self, ctx):
            yield event

    async def run_plan(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in _plan_phase(self, ctx):
            yield event

    async def _maybe_run_deterministic_sql(
        self,
        ctx: PlannerPhaseContext,
        *,
        plan: Any,
        templates: List[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
        """
        Attempt deterministic SQL generation using template matching.

        This method wraps SUPERVISOR_TOOLS.plan_and_select_template for use by
        the sql_stage module, enabling both inline and staged SQL generation
        to share the same deterministic logic.

        Returns:
            Tuple of (result dict with 'sql' and 'template' keys, elapsed_ms) or (None, None)
        """
        import time as time_module
        intent = ctx.intent
        if not intent:
            return None, None
        deterministic_start = time_module.time()
        try:
            result = SUPERVISOR_TOOLS.plan_and_select_template(intent)
            elapsed_ms = int((time_module.time() - deterministic_start) * 1000)
            return result, elapsed_ms
        except Exception as exc:
            logger.debug(
                "[PlannerPipeline] Deterministic SQL generation failed: %s",
                exc,
                exc_info=True,
            )
            return None, None

    async def run_sql_pipeline(
        self,
        ctx: PlannerPhaseContext,
        *,
        intent: IntentModel,
        plan: QueryPlanModel,
        candidate_templates: List[Dict[str, Any]],
        selected_template_id: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute the SQL pipeline (generation, validation, execution).

        This method delegates to run_sql_pipeline_stage in the planner/sql_stage module,
        which centralizes SQL lane logic for reuse across DIRECT, SINGLE_AGENT, and MULTI_AGENT modes.
        """
        async for event in run_sql_pipeline_stage(
            self,
            ctx,
            intent=intent,
            plan=plan,
            candidate_templates=candidate_templates,
            selected_template_id=selected_template_id,
        ):
            yield event

    async def _legacy_run_sql_pipeline(
        self,
        ctx: PlannerPhaseContext,
        *,
        intent: IntentModel,
        plan: QueryPlanModel,
        candidate_templates: List[Dict[str, Any]],
        selected_template_id: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Legacy inline SQL pipeline - preserved for reference during refactor transition."""
        timed_emitter = ctx.timed_emitter
        workflow_start = ctx.workflow_start
        session_id = ctx.session_id
        query = ctx.query
        template = ctx.template

        plan_payload: Optional[Dict[str, Any]] = None
        if hasattr(plan, "model_dump"):
            plan_payload = plan.model_dump()
        elif hasattr(plan, "dict"):
            plan_payload = plan.dict()
        input_payload = {
            "query": query,
            "intent": getattr(intent, "intent_key", None),
            "plan": plan_payload,
            "selected_template_id": selected_template_id,
        }
        receipt = ensure_tool_receipt(
            ctx,
            "sql_chain",
            status="running",
            reused=False,
            attempts=0,
            input_hash=_hash_payload(input_payload),
        )
        start_time = time.time()

        sql = ""
        llm_used = False
        attempt_logs: List[Dict[str, Any]] = []
        validated_attempt: Optional[int] = None
        last_error_code: Optional[str] = None
        last_error_detail: Optional[str] = None
        previous_sql: Optional[str] = None

        progress_message = "Generating SQL with Responses API..."
        deterministic_result: Optional[Dict[str, Any]] = None
        deterministic_elapsed_ms: Optional[int] = None
        try:
            deterministic_start = time.time()
            deterministic_result = SUPERVISOR_TOOLS.plan_and_select_template(intent)
            deterministic_elapsed_ms = int((time.time() - deterministic_start) * 1000)
        except Exception as exc:
            logger.debug(
                "[PlannerExecutor] Deterministic SQL generation failed, falling back to LLM: %s",
                exc,
                exc_info=True,
            )
            deterministic_result = None

        if deterministic_result and isinstance(deterministic_result.get("sql"), str):
            candidate_sql = (deterministic_result.get("sql") or "").strip()
            if candidate_sql:
                sql = candidate_sql
                progress_message = "Using deterministic template SQL"
                template_from_result = deterministic_result.get("template")
                if template_from_result:
                    selected_template_id = template_from_result.get("id") or selected_template_id
                    ctx.template = template_from_result
                attempt_logs.append(
                    {
                        "attempt": 1,
                        "status": "deterministic",
                        "elapsed_ms": deterministic_elapsed_ms or 0,
                        "llm_used": False,
                    }
                )
                receipt.attempts = 1
                validated_attempt = 1

        sql_progress = EventEmitter.progress("sql_compilation", progress_message)
        sql_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield sql_progress
        timed_emitter.start_step("sql_generation")

        if sql and attempt_logs and attempt_logs[-1].get("status") == "deterministic":
            compiled_event = EventEmitter.result(
                "sql_compiled",
                {
                    "sql_length": len(sql),
                    "template_fallback": False,
                    "template_used": selected_template_id,
                    "attempt": attempt_logs[-1].get("attempt", 1),
                    "fallback_reason": None,
                    "llm_used": False,
                },
            )
            compiled_event["event"] = "sql_compiled"
            compiled_event["data"].update(
                {
                    "ts": datetime.utcnow().isoformat(),
                    "elapsed_ms": attempt_logs[-1].get("elapsed_ms"),
                }
            )
            yield compiled_event
            generated_event = EventEmitter.sql_generated(sql)
            generated_event["data"].update(
                {
                    "ts": datetime.utcnow().isoformat(),
                    "elapsed_ms": attempt_logs[-1].get("elapsed_ms"),
                    "llm_used": False,
                    "attempt": attempt_logs[-1].get("attempt", 1),
                }
            )
            yield generated_event
        if not sql:
            MAX_SQL_ATTEMPTS = 3

            messages = await build_sql_messages(
                original_query=query,
                intent=intent,
                plan=plan,
                config_store=self.config_store,
                templates=candidate_templates,
            )

            for attempt in range(1, MAX_SQL_ATTEMPTS + 1):
                attempt_start = time.time()
                attempt_record: Dict[str, Any] = {"attempt": attempt, "status": "started"}
                candidate_sql = ""
                receipt.attempts += 1
                try:
                    if not self.unified_client:
                        self.unified_client = get_unified_client()
                    if not self.unified_client:
                        raise RuntimeError("Unified Responses client is not configured")
                    llm_response, _ = await self.unified_client.simple_completion(
                        messages=messages,
                        reasoning_effort="low",
                    )
                    candidate_sql = (extract_sql_from_response(llm_response) or "").strip()
                    candidate_sql = _normalize_calendar_filters(candidate_sql)
                except Exception as exc:
                    last_error_code = "SQL_GENERATION_ERROR"
                    last_error_detail = str(exc)
                    attempt_record.update(
                        status="error",
                        error_code=last_error_code,
                        error_detail=last_error_detail,
                        elapsed_ms=int((time.time() - attempt_start) * 1000),
                    )
                    attempt_logs.append(attempt_record)
                    error_event = EventEmitter.error(
                        "sql_compilation",
                        "SQL generation failed",
                        details={"attempt": attempt, "error": last_error_detail},
                        code=last_error_code,
                    )
                    error_event["data"]["ts"] = datetime.utcnow().isoformat()
                    yield error_event
                else:
                    if not candidate_sql:
                        last_error_code = "SQL_EMPTY"
                        last_error_detail = "Responses API returned no SQL content."
                        attempt_record.update(
                            status="empty",
                            error_code=last_error_code,
                            error_detail=last_error_detail,
                            elapsed_ms=int((time.time() - attempt_start) * 1000),
                        )
                        attempt_logs.append(attempt_record)
                        empty_notice = EventEmitter.progress(
                            "sql_compilation",
                            "SQL attempt returned no content; retrying with additional guidance.",
                        )
                        empty_notice["data"].update(
                            {"ts": datetime.utcnow().isoformat(), "attempt": attempt}
                        )
                        yield empty_notice
                    else:
                        ok, issues, validate_elapsed = _validate_sql(candidate_sql)
                        attempt_record.update(
                            status="valid" if ok else "invalid",
                            elapsed_ms=int((time.time() - attempt_start) * 1000),
                            validation_elapsed_ms=validate_elapsed,
                            issues=issues,
                        )
                        if not ok:
                            last_error_code = "SQL_VALIDATION_FAILED"
                            last_error_detail = "; ".join(issues) if issues else "Validation failed"
                        attempt_logs.append(attempt_record)
                        if ok:
                            sql = candidate_sql
                            validated_attempt = attempt
                            llm_used = True
                            compiled_event = EventEmitter.result(
                                "sql_compiled",
                                {
                                    "sql_length": len(sql),
                                    "template_fallback": False,
                                    "template_used": selected_template_id,
                                    "attempt": attempt,
                                    "fallback_reason": None,
                                    "llm_used": True,
                                },
                            )
                            compiled_event["event"] = "sql_compiled"
                            compiled_event["data"].update(
                                {
                                    "ts": datetime.utcnow().isoformat(),
                                    "elapsed_ms": attempt_record.get("elapsed_ms"),
                                }
                            )
                            yield compiled_event
                            generated_event = EventEmitter.sql_generated(sql)
                            generated_event["data"].update(
                                {
                                    "ts": datetime.utcnow().isoformat(),
                                    "elapsed_ms": attempt_record.get("elapsed_ms"),
                                    "llm_used": True,
                                    "attempt": attempt,
                                }
                            )
                            yield generated_event
                            break
                        validation_event = EventEmitter.error(
                            "sql_validation",
                            "Generated SQL failed validation",
                            details={"attempt": attempt, "issues": issues},
                            code=last_error_code,
                        )
                        validation_event["data"]["ts"] = datetime.utcnow().isoformat()
                        yield validation_event
                        previous_sql = candidate_sql
                if sql:
                    break
                if attempt < MAX_SQL_ATTEMPTS:
                    retry_notice = EventEmitter.progress(
                        "sql_compilation",
                        f"Retrying SQL generation (attempt {attempt + 1}/{MAX_SQL_ATTEMPTS})",
                    )
                    retry_notice["data"].update(
                        {"ts": datetime.utcnow().isoformat(), "last_error": last_error_code}
                    )
                    yield retry_notice
                    messages = await build_sql_retry_messages(
                        original_query=query,
                        intent=intent,
                        plan=plan,
                        error_code=last_error_code or "unknown_error",
                        error_detail=last_error_detail or "",
                        previous_sql=previous_sql,
                        attempts=attempt_logs,
                        config_store=self.config_store,
                        templates=candidate_templates,
                    )

        generation_status = "generated" if sql else "failed"
        _set_sql_generation_artifact(
            ctx,
            sql=sql if sql else None,
            template_id=selected_template_id,
            attempts=attempt_logs,
            llm_used=llm_used,
            last_error_code=last_error_code,
            last_error_detail=last_error_detail,
            status=generation_status,
        )
        self._capture_artifacts(ctx)
        if sql:
            await self._persist_session_state(ctx, record_sql=True)
        if not sql:
            failure_event = EventEmitter.error(
                "sql_compilation",
                "Unable to generate valid SQL after 3 attempts",
                details={"attempts": attempt_logs, "last_error": last_error_code, "last_detail": last_error_detail},
                code=last_error_code or "SQL_RETRY_EXHAUSTED",
            )
            failure_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield failure_event
            receipt.status = "failed"
            receipt.error = last_error_detail or last_error_code or "SQL_RETRY_EXHAUSTED"
            receipt.elapsed_ms = int((time.time() - start_time) * 1000)
            workflow_abort = EventEmitter.result(
                "workflow_complete",
                {
                    "status": "sql_generation_failed",
                    "total_elapsed_ms": int((time.time() - workflow_start) * 1000),
                },
            )
            workflow_abort["event"] = "workflow_complete"
            workflow_abort["data"]["ts"] = datetime.utcnow().isoformat()
            yield workflow_abort
            ctx.halted = True
            ctx.halt_reason = "sql_generation_failed"
            logger.error(
                "Planner executor halted during SQL generation",
                extra={
                    "session_id": ctx.session_id,
                    "selected_template": ctx.selected_template_id,
                    "attempts": len(attempt_logs),
                    "elapsed_ms": int((time.time() - workflow_start) * 1000),
                },
            )
            return

        validation_progress = EventEmitter.progress(
            "sql_validation", "Validating SQL..."
        )
        validation_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield validation_progress
        ok, issues, validate_elapsed = _validate_sql(sql)
        latest_attempt = validated_attempt
        if latest_attempt is None:
            for entry in reversed(attempt_logs):
                if isinstance(entry, dict) and "attempt" in entry:
                    latest_attempt = entry.get("attempt")
                    break
        validation_event = EventEmitter.result(
            "sql_validated",
            {
                "ok": ok,
                "issues_count": len(issues),
                "attempt": latest_attempt,
                "issues": issues,
            },
        )
        validation_event["event"] = "sql_validated"
        validation_event["data"].update(
            {"ts": datetime.utcnow().isoformat(), "elapsed_ms": validate_elapsed}
        )
        yield validation_event
        if not ok:
            _set_sql_generation_artifact(
                ctx,
                sql=sql,
                template_id=selected_template_id,
                attempts=attempt_logs,
                llm_used=llm_used,
                last_error_code="SQL_VALIDATION_FINAL",
                last_error_detail="; ".join(issues) if issues else None,
                status="validation_failed",
            )
            self._capture_artifacts(ctx)
            error_event = EventEmitter.error(
                "sql_validation",
                "SQL failed validation after retries",
                details={"attempts": attempt_logs, "issues": issues},
                code="SQL_VALIDATION_FINAL",
            )
            error_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield error_event
            workflow_error = EventEmitter.error(
                "workflow_error",
                "SQL query failed validation. Please rephrase your request.",
                code="sql_validation_failed",
                details={
                    "issues": issues,
                    "selected_template": selected_template_id,
                    "attempts": attempt_logs,
                },
            )
            workflow_error["event"] = "workflow_error"
            workflow_error.setdefault("data", {})
            workflow_error["data"]["issues"] = issues
            workflow_error["data"]["ts"] = datetime.utcnow().isoformat()
            yield workflow_error
            receipt.status = "failed"
            receipt.error = "; ".join(issues) if issues else "SQL validation failed"
            receipt.elapsed_ms = int((time.time() - start_time) * 1000)
            workflow_abort = EventEmitter.result(
                "workflow_complete",
                {
                    "status": "sql_validation_failed",
                    "total_elapsed_ms": int((time.time() - workflow_start) * 1000),
                },
            )
            workflow_abort["event"] = "workflow_complete"
            workflow_abort["data"]["ts"] = datetime.utcnow().isoformat()
            yield workflow_abort
            ctx.halted = True
            ctx.halt_reason = "sql_validation_failed"
            logger.error(
                "Planner executor halted during SQL validation",
                extra={
                    "session_id": ctx.session_id,
                    "selected_template": ctx.selected_template_id,
                    "issues": issues,
                    "elapsed_ms": int((time.time() - workflow_start) * 1000),
                },
            )
            return
        else:
            _set_sql_generation_artifact(
                ctx,
                sql=sql,
                template_id=selected_template_id,
                attempts=attempt_logs,
                llm_used=llm_used,
                last_error_code=None,
                last_error_detail=None,
                status="validated",
            )
            self._capture_artifacts(ctx)
        if not ctx.halted:
            receipt.status = "completed"
            receipt.elapsed_ms = int((time.time() - start_time) * 1000)
            receipt.error = None
            if sql:
                receipt.output_hash = _hash_payload({"sql": sql})
        execution_progress = EventEmitter.progress(
            "sql_execution", "Executing query..."
        )
        execution_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield execution_progress
        exec_start = time.time()
        try:
            data = await execute_sql(sql)
            exec_elapsed = int((time.time() - exec_start) * 1000)
            _set_sql_execution_artifact(
                ctx,
                data=data,
                elapsed_ms=exec_elapsed,
                status="success",
            )
            self._capture_artifacts(ctx)
            await self._persist_session_state(
                ctx,
                record_dataset_preview=True,
                record_artifacts=True,
            )

            execution_artifact = getattr(ctx.artifacts, "sql_execution", None)
            row_count = getattr(execution_artifact, "row_count", None) if execution_artifact else None
            columns: List[str] = []
            sample_rows: List[Dict[str, Any]] = []
            if execution_artifact:
                columns = list(getattr(execution_artifact, "columns", []) or [])[:12]
                preview = getattr(execution_artifact, "dataset_preview", None)
                sample_rows = list(preview or getattr(execution_artifact, "sample_rows", []) or [])[:20]

            execution_event = EventEmitter.result(
                "execution_stats",
                {
                    "row_count": row_count,
                    "columns": columns,
                    "columns_count": len(columns),
                },
            )
            execution_event["event"] = "execution_stats"
            execution_event["data"].update(
                {
                    "ts": datetime.utcnow().isoformat(),
                    "elapsed_ms": exec_elapsed,
                    "schedule_stage": "sql",
                    "parallel_group": "core_sequential",
                    "flow_mode": self.flow_mode.value,
                    "lane": "sql",
                    "reused": False,
                }
            )
            yield execution_event

            data_event = EventEmitter.result(
                "data_retrieved",
                {
                    "row_count": row_count,
                    "sample_data": sample_rows,
                },
            )
            data_event["event"] = "data_retrieved"
            data_event["data"].update(
                {
                    "ts": datetime.utcnow().isoformat(),
                    "elapsed_ms": exec_elapsed,
                    "schedule_stage": "sql",
                    "parallel_group": "core_sequential",
                    "flow_mode": self.flow_mode.value,
                    "lane": "sql",
                    "reused": False,
                }
            )
            yield data_event

        except Exception as exec_exc:
            exec_elapsed = int((time.time() - exec_start) * 1000)
            _set_sql_execution_artifact(
                ctx,
                data=None,
                elapsed_ms=exec_elapsed,
                status="error",
                error=str(exec_exc),
                error_code="SQL_EXECUTION_ERROR",
            )
            self._capture_artifacts(ctx)
            logger.error(
                "[SQL_EXECUTION] Execution failed: %s",
                exec_exc,
                extra={
                    "error_code": "SQL_EXECUTION_ERROR",
                    "flow": self.flow_label,
                    "session_id": session_id,
                    "intent_key": intent.intent_key,
                },
            )
            error_event = EventEmitter.error(
                "sql_execution",
                "SQL execution failed",
                details={"error": str(exec_exc)},
                code="SQL_EXECUTION_ERROR",
            )
            error_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield error_event
            receipt.status = "failed"
            receipt.error = str(exec_exc)
            receipt.elapsed_ms = int((time.time() - start_time) * 1000)
            workflow_abort = EventEmitter.result(
                "workflow_complete",
                {
                    "status": "sql_execution_failed",
                    "total_elapsed_ms": int((time.time() - workflow_start) * 1000),
                },
            )
            workflow_abort["event"] = "workflow_complete"
            workflow_abort["data"]["ts"] = datetime.utcnow().isoformat()
            yield workflow_abort
            ctx.halted = True
            ctx.halt_reason = "sql_execution_failed"
            logger.error(
                "Planner executor halted during SQL execution",
                extra={
                    "session_id": ctx.session_id,
                    "selected_template": ctx.selected_template_id,
                    "elapsed_ms": int((time.time() - workflow_start) * 1000),
                },
            )
            return

    async def run_chart_phase(self, ctx: PlannerPhaseContext, *, intent: IntentModel, plan: QueryPlanModel) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute the chart phase (planning, building, emitting events).

        This method delegates to run_chart_pipeline_stage in the planner/chart_stage module,
        which centralizes chart lane logic for reuse across DIRECT, SINGLE_AGENT, and MULTI_AGENT modes.
        """
        async for event in run_chart_pipeline_stage(
            self,
            ctx,
            intent=intent,
            plan=plan,
        ):
            yield event

    async def _legacy_run_chart_phase(self, ctx: PlannerPhaseContext, *, intent: IntentModel, plan: QueryPlanModel) -> AsyncGenerator[Dict[str, Any], None]:
        """Legacy inline chart phase - preserved for reference during refactor transition."""
        plan_payload: Optional[Dict[str, Any]] = None
        if hasattr(plan, "model_dump"):
            plan_payload = plan.model_dump()
        elif hasattr(plan, "dict"):
            plan_payload = plan.dict()
        input_payload = {
            "query": ctx.query,
            "intent": getattr(intent, "intent_key", None),
            "plan": plan_payload,
        }
        receipt = ensure_tool_receipt(
            ctx,
            "chart_builder",
            status="reused" if ctx.reused_chart else "running",
            reused=bool(ctx.reused_chart),
            attempts=0,
            input_hash=_hash_payload(input_payload),
        )
        if ctx.reused_chart:
            cached_payload = compose_chart_ready_payload(ctx)
            if cached_payload:
                cached_chart = _cached_event(
                    "chart_ready",
                    cached_payload,
                    schedule_stage="chart",
                    flow_mode=self.flow_mode,
                    parallel_group="core_sequential",
                    lane="chart",
                )
                yield self._annotate_revision(cached_chart, ctx)
            return
        chart_start = time.time()
        data = _get_sql_dataset(ctx)
        if not data:
            receipt.status = "skipped"
            receipt.elapsed_ms = int((time.time() - chart_start) * 1000)
            return
        query = ctx.query
        chart_progress = EventEmitter.progress(
            "chart_generation", "Planning chart..."
        )
        chart_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield chart_progress
        chart_plan = plan_chart_rule_based(
            data,
            query,
            intent.intent_key,
            statistic=getattr(plan, "statistic", None),
        )
        spec = build_chart_spec(
            data,
            chart_plan.dict(),
            CONFIGS.charts,
            intent_key=intent.intent_key,
            comparison=plan.comparison,
            statistic=getattr(plan, "statistic", None),
        )
        chart_design = _stage_generate_chart_design(intent.intent_key, plan, data, spec)
        spec.setdefault("meta", {}).setdefault("chartDesign", chart_design)
        _set_chart_artifact(
            ctx,
            spec=spec,
            chart_plan=chart_plan,
            chart_design=chart_design,
        )
        self._capture_artifacts(ctx)
        await self._persist_session_state(ctx, record_chart=True)
        chart_elapsed = int((time.time() - chart_start) * 1000)
        receipt.status = "completed"
        receipt.elapsed_ms = chart_elapsed
        receipt.output_hash = _hash_payload(spec)
        chart_event = EventEmitter.result(
            "chart_planned",
            {
                "chart_type": chart_plan.chart_type,
                "series_count": len(chart_plan.series),
            },
        )
        chart_event["event"] = "chart_planned"
        chart_event["data"].update(
            {
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": chart_elapsed,
            }
        )
        yield chart_event
        try:
            ChartSpecModel(**spec)
            generated_chart = EventEmitter.result(
                "chart_generated",
                {
                    "chart_type": spec.get("meta", {}).get("chartDesign", {}).get(
                        "chart_type", "unknown"
                    ),
                    "chart_spec": spec,
                },
                key="chart_spec",
            )
            generated_chart["event"] = "chart_generated"
            generated_chart["data"]["ts"] = datetime.utcnow().isoformat()
            yield generated_chart
        except ValidationError as ve:
            receipt.metadata["validation_warning"] = str(ve)
            warning_event = EventEmitter.progress(
                "warning", f"Chart spec validation warning: {str(ve)}"
            )
            warning_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield warning_event
            fallback_chart = EventEmitter.result(
                "chart_generated",
                {
                    "chart_type": spec.get("meta", {}).get("chartDesign", {}).get(
                        "chart_type", "unknown"
                    ),
                    "chart_spec": spec,
                },
                key="chart_spec",
            )
            fallback_chart["event"] = "chart_generated"
            fallback_chart["data"]["ts"] = datetime.utcnow().isoformat()
            yield fallback_chart
        ready_payload = compose_chart_ready_payload(ctx)
        if ready_payload:
            ready_payload["reused"] = False
            ready_payload.setdefault("schedule_stage", "chart")
            ready_payload.setdefault("parallel_group", "core_sequential")
            ready_payload.setdefault("flow_mode", self.flow_mode.value)
            ready_payload.setdefault("ts", datetime.utcnow().isoformat())
            ready_payload.setdefault("lane", "chart")
            yield self._annotate_revision(
                {
                    "event": "chart_ready",
                    "data": sanitize_for_json(ready_payload),
                },
                ctx,
            )

    async def run_analysis_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        mode_config = get_mode_config(ctx.flow_mode)
        refresh_mode = getattr(ctx, "analysis_refresh_mode", "full")
        receipt = ctx.tool_receipts.get("analysis_synthesis")
        if refresh_mode == "light":
            receipt = ensure_tool_receipt(
                ctx,
                "analysis_synthesis",
                status="reused",
                reused=True,
                attempts=0,
                metadata={"refresh_mode": "light"},
            )
            ctx.reused_analysis = True
            event = _build_reused_analysis_event(self.flow_mode, ctx)
            if event:
                event["data"]["refresh_mode"] = "light"
                yield self._annotate_revision(event, ctx)
            return
        if ctx.reused_analysis:
            receipt = ensure_tool_receipt(
                ctx,
                "analysis_synthesis",
                status="reused",
                reused=True,
                attempts=0,
            )
            return
        if receipt:
            receipt = ensure_tool_receipt(
                ctx,
                "analysis_synthesis",
                status="running",
                reused=False,
                attempts=0,
                metadata={"refresh_mode": refresh_mode},
            )
        else:
            receipt = ensure_tool_receipt(
                ctx,
                "analysis_synthesis",
                status="running",
                reused=False,
                attempts=0,
                metadata={"refresh_mode": refresh_mode},
            )
        data = _get_sql_dataset(ctx)
        if data:
            async for dependency_event in ensure_analysis_dependencies(self, ctx, mode_config=mode_config):
                yield dependency_event
        session_id = ctx.session_id
        query = ctx.query
        sql_artifact = ctx.artifacts.sql_generation
        sql = sql_artifact.sql if sql_artifact and sql_artifact.sql else ""
        chart_artifact = ctx.artifacts.chart
        chart_spec = chart_artifact.spec if chart_artifact and chart_artifact.spec else None
        revision_focus = getattr(ctx, "revision_focus", None)
        if not revision_focus:
            directive_focus = getattr(getattr(ctx, "revision_directive", None), "requested_focus", None)
            if isinstance(directive_focus, str) and directive_focus.strip():
                revision_focus = directive_focus.strip()
        input_payload = {
            "query": query,
            "sql_hash": _hash_payload(sql) if sql else None,
            "chart_present": bool(chart_spec),
            "web_present": bool(ctx.web_search or ctx.artifacts.web),
        }
        if not receipt.input_hash:
            receipt.input_hash = _hash_payload(input_payload)
        receipt.attempts += 1
        analysis_progress = EventEmitter.progress(
            "analysis_generation", "Generating insights..."
        )
        analysis_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield analysis_progress
        analysis_start = time.time()
        full_analysis = ""
        fragments: List[str] = []
        # If the pipeline already resolved clarifications, seed the analysis stream with a short summary
        # of resolved slots to discourage downstream prompts from re-asking.
        if (
            getattr(ctx, "clarifications_needed", None) is False
            and getattr(getattr(ctx, "intent", None), "clarifications_needed", None) is False
        ):
            resolved_slots: List[str] = []
            slot_statuses = getattr(ctx, "slot_statuses", {}) or {}
            for slot_name, status_obj in slot_statuses.items():
                value = None
                if isinstance(status_obj, Mapping):
                    value = status_obj.get("value")
                else:
                    value = getattr(status_obj, "value", None)
                if value:
                    resolved_slots.append(f"{slot_name}: {value}")
            if resolved_slots:
                seed_line = f"Using clarified inputs ({'; '.join(resolved_slots)}). "
                full_analysis += seed_line
                fragments.append(seed_line)
        async for text_chunk in stream_insights_llm(
            data,
            sql,
            query,
            chart_spec=chart_spec,
            search_result=ctx.web_search,
            session_id=session_id,
            focus=revision_focus,
        ):
            if text_chunk:
                full_analysis += text_chunk
                fragments.append(text_chunk)
                streaming_event = {
                    "event": "analysis_streaming",
                    "data": {
                        "step": "analysis_generation",
                        "partial_analysis": text_chunk,
                        "chunk_length": len(text_chunk),
                        "ts": datetime.utcnow().isoformat(),
                    },
                }
                log_analysis_chunk(
                    chunk=text_chunk,
                    step="analysis_generation",
                    role=None,
                    session_id=session_id,
                    flow=getattr(self, "flow_label", None),
                )
                yield streaming_event
        analysis_elapsed = int((time.time() - analysis_start) * 1000)
        analysis_payload = {
            "analysis_length": len(full_analysis),
            "analysis": full_analysis,
        }
        receipt.elapsed_ms = analysis_elapsed
        tldr_summary = _extract_tldr(full_analysis)
        if tldr_summary:
            analysis_payload["tldr"] = tldr_summary
        bullets = _extract_bullets(full_analysis)
        if bullets:
            analysis_payload["bullets"] = bullets
        key_numbers = _extract_key_numbers(full_analysis)
        if key_numbers:
            analysis_payload["key_numbers"] = key_numbers
        risk_watch = _extract_risk_watch(full_analysis)
        if risk_watch:
            analysis_payload["risk_watch"] = risk_watch
        next_steps = _extract_next_steps(full_analysis)
        if next_steps:
            analysis_payload["next_steps"] = next_steps
        tool_bundle = collect_tool_bundle(
            manifest=getattr(ctx, "tool_parallel_manifest", None),
            results=getattr(ctx, "tool_parallel_results", None),
        )
        stock_widget = None
        if tool_bundle:
            stock_widget = tool_bundle.get("stock_widget")
            sources = tool_bundle.get("sources") or {}
            if sources:
                if any(
                    sources.get(alias) == "cached"
                    for alias in ("web_retriever", "web_retriever_cached", "web_retriever_live")
                ):
                    ctx.reused_web = True
                if sources.get("stock_tracker") == "cached":
                    ctx.reused_stock = True
            analysis_payload.update(tool_bundle)
        guardrail_payload = None
        if ctx.web_search:
            web_payload = ctx.web_search.to_payload()
            analysis_payload['web_context'] = web_payload
            guardrail_payload = _evaluate_latency_guardrail(web_payload.get("latency_stats"))
        elif ctx.artifacts.web:
            guardrail_payload = _evaluate_latency_guardrail(ctx.artifacts.web.latency_stats)
        analysis_sources = _build_analysis_source_summaries(
            artifacts=ctx.artifacts,
            tool_sources=tool_bundle.get("sources") if tool_bundle else None,
            stock_widget=analysis_payload.get("stock_widget"),
            web_context=analysis_payload.get("web_context"),
            reused_flags={
                "sql": ctx.reused_sql,
                "stock": ctx.reused_stock,
                "web": ctx.reused_web,
            },
        )
        if analysis_sources:
            analysis_payload["analysis_sources"] = analysis_sources
        if stock_widget:
            _set_market_artifact(ctx, widget=stock_widget)
            self._capture_artifacts(ctx)
        _set_analysis_artifact(
            ctx,
            analysis_text=full_analysis,
            fragments=fragments,
            tool_bundle=tool_bundle or None,
            summary=tldr_summary,
            bullets=bullets,
            key_numbers=key_numbers,
            risk_watch=risk_watch,
            next_steps=next_steps,
        )
        if ctx.artifacts.analysis and ctx.artifacts.analysis.evidence:
            analysis_payload["evidence"] = list(ctx.artifacts.analysis.evidence)
        if guardrail_payload:
            analysis_payload["latency_guardrail"] = guardrail_payload
        analysis_payload["refresh_mode"] = refresh_mode or "full"
        self._capture_artifacts(ctx)
        await self._persist_session_state(ctx, record_analysis=True, tool_bundle=tool_bundle or None)
        receipt.status = "completed"
        receipt.error = None
        receipt.output_hash = _hash_payload(analysis_payload)
        receipt.metadata["fragment_count"] = len(fragments)
        analysis_complete = EventEmitter.result(
            "analysis_complete",
            analysis_payload,
            key="analysis",
        )
        analysis_complete["event"] = "analysis_complete"
        analysis_complete["data"].update(
            {
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": analysis_elapsed,
            }
        )
        yield analysis_complete
        banner_config = FOLLOW_UP_BANNERS.get(ctx.follow_up_route, FOLLOW_UP_BANNERS[FollowUpRoute.FULL_PIPELINE])
        banner_event = EventEmitter.progress("follow_up_route", banner_config["message"])
        banner_event["data"]["ts"] = datetime.utcnow().isoformat()
        banner_event["data"]["schedule_stage"] = "analysis"
        banner_event["data"]["banner"] = {
            "title": banner_config["title"],
            "message": banner_config["message"],
            "route": ctx.follow_up_route.value,
        }
        yield banner_event
        async for accessory_event in self._emit_post_analysis_accessories(ctx):
            yield accessory_event
        from analytics.core.clarify import get_session_store
        session_store = await get_session_store()
        await session_store.cleanup_expired()
        total_elapsed = int((time.time() - ctx.workflow_start) * 1000)
        planner_payload = _build_planner_result_payload(ctx)
        result_event = EventEmitter.result(
            "planner_result", planner_payload
        )
        result_event["event"] = "planner_result"
        result_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield result_event
        workflow_complete = EventEmitter.result(
            "workflow_complete", {"total_elapsed_ms": total_elapsed}
        )
        workflow_complete["event"] = "workflow_complete"
        workflow_complete["data"]["ts"] = datetime.utcnow().isoformat()
        yield workflow_complete


    async def _web_search_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        if not ctx.query or not ctx.query.strip():
            return
    
        progress = EventEmitter.progress("web_search", "Gathering latest market headlines...")
        progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield progress

        if not self.response_search.has_api_key():
            summary = "Web search disabled until GOOGLE_API_KEY or GEMINI_API_KEY is configured."
            payload = {
                "ready": False,
                "error": "search_api_missing",
                "summary": summary,
            }
            card = {
                "type": "web_context",
                "state": "error",
                "message": summary,
            }
            _set_web_artifact(ctx, payload=payload, topic=None, search_result=None)
            self._capture_artifacts(ctx)
            result_event = EventEmitter.result("web_search", {"web_context": payload, "specialist_card": card})
            result_event["data"]["ts"] = datetime.utcnow().isoformat()
            result_event["data"]["specialist_card"] = card
            result_event["data"]["schedule_stage"] = "accessories_post"
            yield result_event
            return
    
        context_parts: List[str] = []
        intent = ctx.intent
        if intent and getattr(intent, "intent_key", None):
            context_parts.append(f"intent={intent.intent_key}")
        slots = getattr(intent, "slots_detected", {}) or {}
        company_slot = slots.get("company") if isinstance(slots, dict) else None
        tickers: List[str] = []
        if isinstance(company_slot, str) and company_slot.strip():
            tickers.append(company_slot.strip().upper())
        elif isinstance(company_slot, (list, tuple, set)):
            for value in company_slot:
                if isinstance(value, str) and value.strip():
                    tickers.append(value.strip().upper())
        if tickers:
            context_parts.append("tickers=" + ", ".join(tickers[:3]))
        plan = ctx.plan or ctx.provisional_plan
        if plan and getattr(plan, "metrics", None):
            metrics = list(getattr(plan, "metrics", []) or [])
            if metrics:
                context_parts.append("metrics=" + ", ".join(metrics[:3]))
        if ctx.assumptions:
            context_parts.append("assumptions=" + "; ".join(str(item) for item in ctx.assumptions[:2]))
    
        context_hint = " | ".join(context_parts) if context_parts else None
    
        topic: Optional[str] = None
        try:
            # First, compute and surface the rewritten search topic
            try:
                topic = await self.response_search.generate_topic(ctx.query, session_id=ctx.session_id)
            except Exception:
                topic = None
            if topic:
                topic_event = EventEmitter.progress("web_search", f"Search topic: {topic}")
                topic_event["data"]["ts"] = datetime.utcnow().isoformat()
                yield topic_event

            # Then, perform the actual web search using that topic
            search_result = await self.response_search.perform_search(
                ctx.query,
                session_id=ctx.session_id,
                context=context_hint,
                search_topic=topic,
            )
        except ResponseSearchError as exc:
            error_event = EventEmitter.error(
                "web_search",
                "Latest news search failed",
                details={"error": str(exc)},
                code="WEB_SEARCH_ERROR",
            )
            error_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield error_event
            error_payload = {
                "ready": False,
                "error": "WEB_SEARCH_ERROR",
                "summary": str(exc),
            }
            _set_web_artifact(ctx, payload=error_payload, topic=None, search_result=None)
            self._capture_artifacts(ctx)
            return
    
        ctx.web_search = search_result
        payload = search_result.to_payload()
        payload["ready"] = True
        payload["ts"] = datetime.utcnow().isoformat()
        _set_web_artifact(ctx, payload=payload, topic=topic, search_result=search_result)
        self._capture_artifacts(ctx)
        await self._persist_session_state(ctx, record_web=True, record_artifacts=False)
        card = {
            "type": "web_context",
            "state": "ready",
            "topic": payload.get("search_topic") or topic,
            "summary": payload.get("summary"),
            "snippets": payload.get("snippets", []),
        }
        event_payload = {
            "web_context": payload,
            "specialist_card": card,
        }
        if payload.get("questions"):
            event_payload["questions"] = payload.get("questions")
        result_event = EventEmitter.result("web_search", event_payload)
        result_event["data"]["ts"] = datetime.utcnow().isoformat()
        result_event["data"]["specialist_card"] = card
        result_event["data"]["schedule_stage"] = "accessories_post"
        yield result_event
    
    def _get_company_display(self, intent: IntentModel, provisional_plan: Optional[QueryPlanModel] = None) -> str:
        """Generate smart company display based on intent and plan context."""
        company = intent.slots_detected.get('company')
        comparison = provisional_plan.comparison if provisional_plan else None
        # Smart display based on context
        if comparison == 'all':
            return 'All Companies'
        elif comparison == 'vs_avg':
            return 'Industry Average'
        elif company:
            return company
        else:
            return 'Unknown'

    async def emit_analysis_revision(
        self,
        *,
        session_id: str,
        analysis: str,
        reason: Optional[str] = None,
        source: Optional[str] = None,
        repository: Optional[Any] = None,
        hooks: Optional[AnalyticsFlowHooks] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        stream = _analysis_revision_emit(
            session_id=session_id,
            analysis=analysis,
            reason=reason,
            source=source,
            repository=repository,
        )
        if hooks is None:
            async for event in stream:
                yield event
            return

        hook_ctx: Dict[str, Any] = {"session_id": session_id}
        try:
            async for start_event in hooks.on_flow_start(hook_ctx):
                yield start_event
            async for event in stream:
                async for pre_event in hooks.before_event(hook_ctx, event):
                    yield pre_event
                yield event
                async for post_event in hooks.after_event(hook_ctx, event):
                    yield post_event
        except BaseException as exc:
            async for end_event in hooks.on_flow_end(hook_ctx, error=exc):
                yield end_event
            raise
        else:
            async for end_event in hooks.on_flow_end(hook_ctx):
                yield end_event

    async def events(
        self,
        query: str,
        session_id: Optional[str] = None,
        *,
        revision_requested: bool = False,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        "Enhanced workflow with structured decision events and timing."
        ctx = await _initialize_context(self, query, session_id)
        session_id = ctx.session_id
        timed_emitter = ctx.timed_emitter
        yield EventEmitter.session_started(session_id)

        from .pipeline_tools import get_planner_tool_registry  # Local import to avoid circular dependency

        registry = get_planner_tool_registry()
        executed: Set[str] = set()
        mode_config = get_mode_config(self.flow_mode)
        run_tools_supported = asyncio.iscoroutinefunction(run_tool_parallelism)
        setattr(self, "_run_tools_supported", run_tools_supported)
        if not run_tools_supported:
            self._suppress_fresh_pipeline = True
        tool_runtime: Optional[ToolParallelRuntime] = None
        tool_state: Optional[Dict[str, Any]] = None
        is_session_follow_up = bool(getattr(ctx, "session_follow_up", False))
        fresh_run = not is_session_follow_up
        explicit_revision_targets = set(getattr(self, "revision_targets", set()) or set())
        ctx.force_full_fresh_pipeline = (
            fresh_run and ctx.follow_up_route == FollowUpRoute.FULL_PIPELINE and not explicit_revision_targets
        )
        forced_refresh = dict(getattr(ctx, "lane_refresh_required", {}) or {})
        if fresh_run:
            # Always refresh market/web on fresh runs; other lanes honor follow-up route.
            forced_refresh["web"] = True
            forced_refresh["market"] = True
            ctx.lane_refresh_required = forced_refresh
        if ctx.force_full_fresh_pipeline:
            ctx.parallelism_enabled = True
            ctx.revision_targets = set()
            ctx.revision_hint_active = False
            ctx.revision_id = None
            ctx.reuse_sql = False
            ctx.reused_sql = False
            ctx.reused_chart = False
            ctx.reused_analysis = False
            ctx.reused_web = False
            ctx.reused_stock = False
            ctx.reuse_snapshot_active = False
        skip_deterministic = bool(revision_requested)
        ctx.revision_requested = skip_deterministic
        is_revision_follow_up = (
            skip_deterministic
            or is_session_follow_up
            or ctx.follow_up_route != FollowUpRoute.FULL_PIPELINE
            or bool(getattr(ctx, "revision_targets", None))
        )
        setattr(ctx, "is_revision_follow_up", is_revision_follow_up)
        lane_rebuild_notice_emitted = False

        try:
            if skip_deterministic:
                executed.update({"classification", "intent_detection", "clarification", "plan_generation"})
                revision_ctx = getattr(ctx, "revision_context", None)
                payload = getattr(revision_ctx, "snapshot_payload", None) if revision_ctx else None
                if isinstance(payload, Mapping):
                    _hydrate_revision_payload(ctx, payload)
                if ctx.classification is None:
                    ctx.is_financial_query = True
                elif getattr(ctx.classification, "is_financial_query", None) is not None:
                    ctx.is_financial_query = bool(ctx.classification.is_financial_query)
                await self._persist_session_state(ctx, record_artifacts=True)
            elif is_revision_follow_up:
                executed.add("classification")
                executed.add("clarification")
                classification_artifact = getattr(ctx.artifacts, "classification", None)
                if classification_artifact is not None:
                    is_financial = getattr(classification_artifact, "is_financial", None)
                    if is_financial is not None:
                        ctx.is_financial_query = bool(is_financial)
                    if getattr(ctx, "classification", None) is None:
                        raw_payload = getattr(classification_artifact, "raw", None)
                        if isinstance(raw_payload, dict):
                            try:
                                ctx.classification = OffTopicClassifierSchema.model_validate(raw_payload)
                            except Exception:
                                pass
                else:
                    ctx.is_financial_query = True
                await self._persist_session_state(ctx, record_artifacts=True)
            else:
                async for event in registry.invoke("classification", self, ctx, executed=executed):
                    yield event
                await self._persist_session_state(ctx, record_artifacts=True)
                if not ctx.is_financial_query:
                    return

            tool_sequence: Tuple[str, ...]
            if skip_deterministic:
                tool_sequence = ()
            elif is_revision_follow_up:
                needs_intent = ctx.intent is None
                needs_plan = (ctx.plan or ctx.provisional_plan) is None
                if needs_intent:
                    tool_sequence = ("intent_detection",)
                else:
                    tool_sequence = ()
                    executed.add("intent_detection")
                if needs_plan:
                    tool_sequence = tool_sequence + ("plan_generation",)
                else:
                    executed.add("plan_generation")
            else:
                tool_sequence = ("intent_detection", "clarification", "plan_generation")
            for tool_name in tool_sequence:
                async for event in registry.invoke(tool_name, self, ctx, executed=executed):
                    yield event
                await self._persist_session_state(ctx, record_artifacts=True)

            if ctx.intent is None or (ctx.plan or ctx.provisional_plan) is None:
                return

            fanout_adapters: Tuple[Any, ...] = self._fanout_adapters_for_context(ctx)
            should_run_parallel = (
                ctx.parallelism_enabled
                and bool(fanout_adapters)
                and not (ctx.reuse_sql and ctx.reuse_snapshot_active)
            )
            if should_run_parallel and not run_tools_supported:
                should_run_parallel = False
            if should_run_parallel:
                tool_runtime = self._start_tool_parallelism(
                    ctx,
                    adapters=fanout_adapters,
                )
                runtime_has_workers = bool(getattr(tool_runtime, "runner", None) or getattr(tool_runtime, "dispatcher", None))
                if not runtime_has_workers:
                    try:
                        tool_runtime.queue.put_nowait(_TOOL_QUEUE_SENTINEL)
                    except Exception:
                        pass
                tool_state = {"queue": tool_runtime.queue, "active": runtime_has_workers, "runtime": tool_runtime}
                for tool_event in collect_tool_deltas_now(self, tool_state, ctx):
                    yield tool_event

            if ctx.force_full_fresh_pipeline:
                revision_targets = set()
                run_sql_lane = True
                run_chart_lane = True
                run_analysis_lane = True
                stock_only_run = False
                ctx.stock_only = False
            else:
                derived_targets = derive_revision_targets(ctx, intent_lane_map=_INTENT_LANE_HINTS)
                revision_plan = build_revision_plan(ctx, targets=derived_targets)
                apply_revision_plan(ctx, revision_plan)
                revision_targets: Set[str] = set(revision_plan.targets)
                run_sql_lane = revision_plan.run_sql_lane
                run_chart_lane = revision_plan.run_chart_lane
                run_analysis_lane = revision_plan.run_analysis_lane
                stock_only_run = revision_plan.stock_only
            # Telemetry snapshot of the computed revision plan to aid debugging
            telemetry.revision_plan(
                session_id=ctx.session_id,
                flow=self.flow_label,
                targets=sorted(revision_targets),
                run_sql_lane=run_sql_lane,
                run_chart_lane=run_chart_lane,
                run_analysis_lane=run_analysis_lane,
                stock_only=stock_only_run,
                follow_up_route=(ctx.follow_up_route.value if getattr(ctx, 'follow_up_route', None) else None),
                revision_id=getattr(ctx, 'revision_id', None),
            )

            lane_executors = build_pipeline_lane_executors(
                self,
                ctx=ctx,
                registry=registry,
                executed=executed,
                tool_state=tool_state,
                mode_config=mode_config,
                run_sql_lane=run_sql_lane,
                run_chart_lane=run_chart_lane,
            )

            if revision_targets:
                follow_up_route = getattr(self, "follow_up_route", None)
                revision_event = annotate_revision_event(
                    build_revision_request_event(
                        ctx,
                        flow_mode_value=self.flow_mode.value,
                        follow_up_route_value=follow_up_route.value if follow_up_route is not None else None,
                    ),
                    ctx,
                )
                yield revision_event
            if revision_requested and not lane_rebuild_notice_emitted:
                lanes_for_notice = sorted(revision_targets) if revision_targets else []
                if not lanes_for_notice:
                    refresh_flags = getattr(ctx, "lane_refresh_required", {}) or {}
                    lanes_for_notice = sorted(
                        lane for lane, required in refresh_flags.items() if required
                    )
                if not lanes_for_notice:
                    lanes_for_notice = ["analysis", "chart", "web", "market"]
                rebuild_event = EventEmitter.status(
                    "lane_rebuild_notice",
                    "Rebuilding requested revision lanes.",
                )
                rebuild_event.setdefault("data", {})
                rebuild_event["data"].update(
                    {
                        "lanes": lanes_for_notice,
                        "revision": True,
                        "session_id": ctx.session_id,
                        "reason": "revision_requested",
                        "follow_up_route": ctx.follow_up_route.value,
                    }
                )
                yield rebuild_event
                lane_rebuild_notice_emitted = True

            start_sql = maybe_emit_fresh_lane_event(self, ctx, "sql", "started")
            if start_sql:
                yield start_sql
            try:
                async for event in lane_executors.sql.run():
                    yield event
            except Exception:
                fail_sql = maybe_emit_fresh_lane_event(self, ctx, "sql", "failed")
                if fail_sql:
                    yield fail_sql
                raise
            else:
                complete_sql = maybe_emit_fresh_lane_event(self, ctx, "sql", "completed")
                if complete_sql:
                    yield complete_sql

            accessory_lanes: Tuple[str, ...] = ()
            if ctx.force_full_fresh_pipeline:
                accessory_lanes = ("web", "stock")
                for lane in accessory_lanes:
                    start_lane = maybe_emit_fresh_lane_event(self, ctx, lane, "started")
                    if start_lane:
                        yield start_lane

            try:
                async for event in self._stream_with_tool_state(
                    ensure_analysis_dependencies(self, ctx, mode_config=mode_config),
                    tool_state,
                    ctx,
                ):
                    yield event
            except Exception:
                for lane in accessory_lanes:
                    fail_lane = maybe_emit_fresh_lane_event(self, ctx, lane, "failed")
                    if fail_lane:
                        yield fail_lane
                raise

            if stock_only_run:
                ctx.reused_stock = False
                if tool_state and tool_state.get("active", False):
                    async for tool_event in drain_tool_state_async(self, tool_state, ctx):
                        yield tool_event
                else:
                    ad_hoc_runtime = self._start_tool_parallelism(
                        ctx,
                        adapters=(StockTrackerAdapter(),),
                        concurrency_override=1,
                    )
                    ad_hoc_state = {"queue": ad_hoc_runtime.queue, "active": True, "runtime": ad_hoc_runtime}
                    try:
                        async for tool_event in drain_tool_state_async(self, ad_hoc_state, ctx):
                            yield tool_event
                    finally:
                        await ad_hoc_runtime.close()
                await self._persist_session_state(ctx, record_artifacts=True)
                analysis_event = _build_reused_analysis_event(self.flow_mode, ctx)
                if analysis_event:
                    yield self._annotate_revision(analysis_event, ctx)
                banner_config = FOLLOW_UP_BANNERS.get(ctx.follow_up_route, FOLLOW_UP_BANNERS[FollowUpRoute.FULL_PIPELINE])
                banner_event = EventEmitter.progress("follow_up_route", banner_config["message"])
                banner_event["data"]["route"] = ctx.follow_up_route.value
                banner_event["data"]["ts"] = datetime.utcnow().isoformat()
                yield self._annotate_revision(banner_event, ctx)
                planner_payload = _build_planner_result_payload(ctx)
                result_event = EventEmitter.result("planner_result", planner_payload)
                result_event["event"] = "planner_result"
                result_event["data"]["ts"] = datetime.utcnow().isoformat()
                yield self._annotate_revision(result_event, ctx)
                total_elapsed = int((time.time() - ctx.workflow_start) * 1000)
                workflow_complete = EventEmitter.result("workflow_complete", {"total_elapsed_ms": total_elapsed})
                workflow_complete["event"] = "workflow_complete"
                workflow_complete["data"]["ts"] = datetime.utcnow().isoformat()
                yield self._annotate_revision(workflow_complete, ctx)
                return

            if ctx.halted:
                return

            start_chart = maybe_emit_fresh_lane_event(self, ctx, "chart", "started")
            if start_chart:
                yield start_chart
            try:
                async for event in lane_executors.chart.run():
                    yield event
            except Exception:
                fail_chart = maybe_emit_fresh_lane_event(self, ctx, "chart", "failed")
                if fail_chart:
                    yield fail_chart
                raise
            else:
                complete_chart = maybe_emit_fresh_lane_event(self, ctx, "chart", "completed")
                if complete_chart:
                    yield complete_chart

            start_analysis = maybe_emit_fresh_lane_event(self, ctx, "analysis", "started")
            if start_analysis:
                yield start_analysis
            try:
                async for event in lane_executors.analysis.run():
                    yield event
            except Exception:
                fail_analysis = maybe_emit_fresh_lane_event(self, ctx, "analysis", "failed")
                if fail_analysis:
                    yield fail_analysis
                raise
            else:
                complete_analysis = maybe_emit_fresh_lane_event(self, ctx, "analysis", "completed")
                if complete_analysis:
                    yield complete_analysis
        finally:
            if tool_runtime:
                await tool_runtime.close()


async def _initialize_context(self, query: str, session_id: Optional[str]) -> PlannerPhaseContext:
    workflow_start = time.time()
    resolved_session = session_id or str(uuid.uuid4())
    timed_emitter = TimedEventEmitter(session_id=resolved_session, flow=self.flow_label)
    ctx = PlannerPhaseContext(
        query=query,
        session_id=resolved_session,
        workflow_start=workflow_start,
        timed_emitter=timed_emitter,
        flow_mode=self.flow_mode,
        configs=CONFIGS.__dict__,
        parallelism_enabled=self.parallelism_enabled,
        follow_up_route=self.follow_up_route,
        reuse_sql=self.follow_up_route == FollowUpRoute.REUSE_SQL,
        stock_only=self.follow_up_route == FollowUpRoute.STOCK_ONLY,
    )
    self._agent_tool_counters.clear()
    self._agent_tool_active_ids.clear()
    ctx.session_follow_up = bool(getattr(self, "session_follow_up", False))
    prefetched_snapshot = getattr(self, "_prefetched_snapshot", None)
    snapshot_has_lanes = False
    if isinstance(prefetched_snapshot, SessionStateSnapshot):
        receipts = (prefetched_snapshot.tool_cache or {}).get("tool_receipts") if hasattr(prefetched_snapshot, "tool_cache") else None
        snapshot_has_lanes = bool(
            (getattr(prefetched_snapshot, "lane_timestamps", None) or {})
            or (getattr(prefetched_snapshot, "lane_refresh_overrides", None) or {})
            or (receipts or {})
        )
    hydrate_from_snapshot = bool(ctx.session_follow_up) or self.follow_up_route != FollowUpRoute.FULL_PIPELINE or snapshot_has_lanes
    snapshot = prefetched_snapshot if hydrate_from_snapshot else None
    snapshot_artifacts = _artifacts_from_snapshot(snapshot)
    revision_snapshot = extract_revision_snapshot(snapshot)
    if hydrate_from_snapshot and (snapshot_artifacts or revision_snapshot):
        _hydrate_context_from_snapshot(ctx, snapshot, snapshot_artifacts)
    else:
        ctx.revision_snapshot = None
        ctx.prior_intent_signature = None
    if (
        hydrate_from_snapshot
        and not snapshot_artifacts
        and not revision_snapshot
        and self.follow_up_route == FollowUpRoute.REUSE_SQL
        and self._latest_artifacts is not None
    ):
        cloned_artifacts = copy.deepcopy(self._latest_artifacts)
        ctx.artifacts = copy.deepcopy(cloned_artifacts)
        ctx.snapshot_artifacts = copy.deepcopy(cloned_artifacts)
    revision_targets = set(getattr(self, "revision_targets", set()) or set())
    hint_active = bool(getattr(self, "revision_hint_active", False) and revision_targets)
    ctx.revision_targets = set(revision_targets)
    ctx.revision_hint_active = hint_active if revision_targets else False
    if ctx.revision_targets:
        ctx.revision_id = str(uuid.uuid4())
        ctx.parallelism_enabled = True
    directive = getattr(self, "revision_directive", None)
    if directive is not None:
        ctx.revision_directive = directive
        ctx.agentic_revision_mode = bool(getattr(self, "agentic_revision_mode", False) or getattr(directive, "agentic", False))
    else:
        ctx.revision_directive = None
        ctx.agentic_revision_mode = bool(getattr(self, "agentic_revision_mode", False))
    ctx.lane_refresh_required = dict(getattr(self, "_lane_refresh_required", {}))
    ctx.analysis_refresh_mode = getattr(self, "_analysis_refresh_mode", "full")
    if hydrate_from_snapshot and snapshot is not None:
        ctx.revision_context = PlannerRevisionContext.from_snapshot(
            snapshot,
            lane_refresh_overrides=ctx.lane_refresh_required,
        )
    else:
        ctx.revision_context = None
    if snapshot is not None and self.follow_up_route == FollowUpRoute.FULL_PIPELINE and ctx.revision_context is not None:
        lane_refresh_flags = dict(getattr(ctx, "lane_refresh_required", {}) or {})
        lane_refresh_flags.setdefault("web", True)
        lane_refresh_flags.setdefault("market", True)
        ctx.lane_refresh_required = lane_refresh_flags
        overrides = dict(getattr(ctx.revision_context, "lane_refresh_overrides", {}) or {})
        overrides["web"] = True
        overrides["market"] = True
        ctx.revision_context.lane_refresh_overrides = overrides
        if getattr(snapshot, "lane_timestamps", None) is not None:
            snapshot.lane_timestamps.pop("web", None)
            snapshot.lane_timestamps.pop("market", None)
        if getattr(snapshot, "tool_cache", None):
            receipts = snapshot.tool_cache.get("tool_receipts") or {}
            receipts.pop("web_retriever", None)
            receipts.pop("stock_tracker", None)
            snapshot.tool_cache["tool_receipts"] = receipts
    if ctx.revision_context and ctx.revision_context.receipts:
        ctx.tool_receipts.update(ctx.revision_context.receipts)
    _apply_revision_context_hints(ctx)
    return ctx


async def _classification_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
    async for event in run_classification_stage(self, ctx):
        yield event

async def _intent_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
    async for event in run_intent_stage(self, ctx):
        yield event

async def _clarification_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
    async for event in run_clarification_stage(self, ctx):
        yield event

async def _plan_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
    intent = ctx.intent
    provisional_plan = ctx.provisional_plan
    template = ctx.template
    if intent is None or provisional_plan is None:
        return
    ctx.plan = provisional_plan
    ctx.reused_sql = False
    ctx.reused_chart = False
    ctx.reused_stock = False
    ctx.reused_web = False
    ctx.reused_analysis = False
    ctx.web_search_seeded = False
    ctx.stock_widget_seeded = False
    ctx.stock_ready_emitted = False
    ctx.web_ready_emitted = False
    ctx.tool_parallel_results = []
    ctx.tool_parallel_manifest = []
    current_signature = build_intent_signature(intent, ctx.plan)
    ctx.intent_signature = current_signature
    prior_signature = ctx.prior_intent_signature
    if prior_signature and current_signature:
        ctx.criteria_changed = not signatures_equal(prior_signature, current_signature)
    elif prior_signature and current_signature is None:
        ctx.criteria_changed = True
    else:
        ctx.criteria_changed = False
    ctx.snapshot_age_seconds = (
        _snapshot_age_seconds_from_snapshot(ctx.revision_snapshot) if ctx.revision_snapshot else None
    )
    snapshot_fresh = _is_snapshot_fresh(ctx.revision_snapshot)
    ctx.snapshot_stale = bool(ctx.revision_snapshot) and not snapshot_fresh
    ctx.reuse_snapshot_active = snapshot_fresh and not ctx.criteria_changed
    if ctx.follow_up_route == FollowUpRoute.REUSE_SQL and ctx.reuse_snapshot_active:
        ctx.reuse_sql = current_signature is not None
    else:
        ctx.reuse_sql = False
    intent_finalized_event = {
        "event": "intent_finalized",
        "data": {
            "intent_key": intent.intent_key,
            "confidence": intent.confidence,
            "assumptions": ctx.assumptions,
            "ts": datetime.utcnow().isoformat(),
        },
    }
    if ctx.clarification_rounds:
        intent_finalized_event["data"]["clarification_rounds"] = ctx.clarification_rounds
    yield intent_finalized_event
    criteria_model = intent_to_sql_criteria(intent, CONFIGS.__dict__)
    criteria_payload = criteria_model.model_dump()
    criteria_payload["ts"] = datetime.utcnow().isoformat()
    yield {
        "event": "criteria_ready",
        "data": criteria_payload,
    }
    elapsed_ms = int((time.time() - ctx.workflow_start) * 1000)
    plan_event = EventEmitter.result(
        "plan_built",
        {
            "granularity": provisional_plan.granularity,
            "comparison": provisional_plan.comparison,
            "metrics_count": len(provisional_plan.metrics),
        },
    )
    plan_event["event"] = "plan_built"
    plan_event["data"].update(
        {
            "ts": datetime.utcnow().isoformat(),
            "elapsed_ms": elapsed_ms,
            "parallelism_enabled": ctx.parallelism_enabled,
        }
    )
    yield plan_event
    template_info = None
    if template and intent.intent_key:
        queries_config = CONFIGS.__dict__.get("queries", {})
        patterns = queries_config.get("query_patterns", {})
        if intent.intent_key in patterns:
            pattern = patterns[intent.intent_key]
            template_info = {
                "id": intent.intent_key,
                "name": pattern.get("name", intent.intent_key),
                "description": pattern.get(
                    "description", "No description available"
                ),
            }
    template_event = EventEmitter.result(
        "template_selected",
        {
            "template_id": intent.intent_key if template else None,
            "has_template": template is not None,
        },
    )
    template_event["event"] = "template_selected"
    template_event["data"]["ts"] = datetime.utcnow().isoformat()
    if template_info:
        template_event["data"]["template"] = template_info
    yield template_event
    catalog_lookup_start = time.time()
    candidate_templates: List[Dict[str, Any]] = []
    try:
        candidate_templates = await fetch_templates_for_intent(
            intent,
            query=ctx.query,
            top_k=3,
            store=self.config_store,
        )
    except Exception as catalog_error:
        logger.warning("[SQL_CATALOG] Template lookup failed: %s", catalog_error)
    catalog_elapsed = int((time.time() - catalog_lookup_start) * 1000)
    selected_template_id = None
    if isinstance(template, dict):
        selected_template_id = template.get("id") or template.get("name")
    if candidate_templates:
        catalog_event = EventEmitter.catalog_trace(
            "sql_compilation",
            templates=candidate_templates,
            intent_key=intent.intent_key,
            query=ctx.query,
            selected_template=selected_template_id,
            elapsed_ms=catalog_elapsed,
            session_id=ctx.session_id,
            flow=getattr(self, "flow_label", None),
        )
        catalog_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield catalog_event
    ctx.candidate_templates = candidate_templates
    ctx.selected_template_id = selected_template_id
    plan_payload = provisional_plan.model_dump()
    candidate_payload = [dict(template) for template in candidate_templates]
    template_payload = template_info or (template if isinstance(template, dict) else None)
    ctx.artifacts.plan = PlanArtifact(
        query=ctx.query,
        plan=plan_payload,
        candidate_templates=candidate_payload,
        selected_template_id=selected_template_id,
        comparison=provisional_plan.comparison,
        granularity=provisional_plan.granularity,
        metrics_count=len(provisional_plan.metrics),
        template=template_payload,
        parallelism_enabled=ctx.parallelism_enabled,
        criteria={k: v for k, v in criteria_payload.items() if k != "ts"},
        catalog_elapsed_ms=catalog_elapsed,
    )
    self._capture_artifacts(ctx)

class PlannerExecutorFlow:
    """Backward-compatible wrapper around :class:`PlannerPipeline`."""

    _PROMPT_VERSIONS: Dict[str, str] = {
        "schema_clarifier": "2025-10-16",
        "multi_agent.supervisor": "2025-10-16",
    }
    _THOUGHT_EVENT_NAMES = frozenset(
        {
            "progress",
            "status",
            "classification_started",
            "classification_reasoning",
        }
    )
    _THOUGHT_EVENT_STEP_OVERRIDES: Dict[str, str] = {
        "classification_started": "classification",
        "classification_reasoning": "classification",
    }
    _THOUGHT_COMPLETION_EVENTS: Dict[str, str] = {
        "classification_complete": "classification",
        "classification_declined": "classification",
        "final_answer": "classification",
        "clarification_complete": "clarification",
        "clarification_failed": "clarification",
        "clarification_skipped": "clarification",
        "clarification_timeout": "clarification",
    }

    @classmethod
    def get_prompt_versions(cls) -> Dict[str, str]:
        return dict(cls._PROMPT_VERSIONS)

    def __init__(
        self,
        *,
        flow_mode: FlowMode = FlowMode.DIRECT,
        parallelism_enabled: Optional[bool] = None,
        response_search: Optional[ResponseSearchDependencies] = None,
    ) -> None:
        self._pipeline = PlannerPipeline(
            flow_mode=flow_mode,
            parallelism_enabled=parallelism_enabled,
            response_search=response_search,
        )
        self.flow_mode = flow_mode
        self.follow_up_route = FollowUpRoute.FULL_PIPELINE
        self._prompt_versions = dict(self._PROMPT_VERSIONS)
        self._thought_counters: Dict[str, int] = {}
        self._last_thoughts: Dict[str, str] = {}
        self._suppress_fresh_pipeline = False

    def __getattr__(self, name: str):
        try:
            return getattr(self._pipeline, name)
        except AttributeError:
            raise AttributeError(name) from None

    def __setattr__(self, name: str, value):
        if name == '_pipeline':
            super().__setattr__(name, value)
        elif hasattr(self, '_pipeline') and hasattr(self._pipeline, name):
            setattr(self._pipeline, name, value)
        else:
            super().__setattr__(name, value)

    def latest_artifacts(self) -> Optional[PipelineArtifacts]:
        return self._pipeline.latest_artifacts()

    @property
    def tool_registry(self):
        return self._pipeline.tool_registry

    def invoke_tool(
        self,
        name: str,
        ctx: PlannerPhaseContext,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        return self.tool_registry.invoke(name, self._pipeline, ctx, **kwargs)

    def prime_with_snapshot(self, snapshot: Optional[SessionStateSnapshot]) -> None:
        self._pipeline.prime_with_snapshot(snapshot)

    def set_follow_up_route(self, route: FollowUpRoute) -> None:
        self.follow_up_route = route
        self._pipeline.set_follow_up_route(route)

    def set_session_follow_up(self, follow_up: bool) -> None:
        self.session_follow_up = bool(follow_up)
        self._pipeline.set_session_follow_up(follow_up)

    def set_revision_targets(self, targets: Iterable[str]) -> None:
        self._pipeline.set_revision_targets(targets)

    def set_revision_directive(self, directive: Optional["RevisionDirective"]) -> None:
        self._pipeline.set_revision_directive(directive)
        self.agentic_revision_mode = bool(directive.agentic if directive else False)

    def set_lane_refresh_requirements(self, requirements: Optional[Mapping[str, Any]]) -> None:
        self._pipeline.set_lane_refresh_requirements(requirements)

    def set_analysis_refresh_mode(self, mode: Optional[str]) -> None:
        self._pipeline.set_analysis_refresh_mode(mode)

    async def initialize_context(self, query: str, session_id: Optional[str] = None) -> PlannerPhaseContext:
        return await self._pipeline.initialize_context(query, session_id)

    async def emit_chart_patch(
        self,
        *,
        session_id: str,
        patch: Dict[str, Any],
        reason: Optional[str] = None,
        source: Optional[str] = None,
        repository: Optional[Any] = None,
        hooks: Optional[AnalyticsFlowHooks] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self._thought_counters.clear()
        self._last_thoughts.clear()
        stream = self._pipeline.emit_chart_patch(
            session_id=session_id,
            patch=patch,
            reason=reason,
            source=source,
            repository=repository,
            hooks=hooks,
        )
        async for event in stream:
            yield event

    async def emit_analysis_revision(
        self,
        *,
        session_id: str,
        analysis: str,
        reason: Optional[str] = None,
        source: Optional[str] = None,
        repository: Optional[Any] = None,
        hooks: Optional[AnalyticsFlowHooks] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self._thought_counters.clear()
        self._last_thoughts.clear()
        stream = self._pipeline.emit_analysis_revision(
            session_id=session_id,
            analysis=analysis,
            reason=reason,
            source=source,
            repository=repository,
            hooks=hooks,
        )
        async for event in stream:
            yield event

    def _attach_thought_metadata(self, event: Dict[str, Any]) -> None:
        event_name = event.get("event")
        if event_name not in self._THOUGHT_EVENT_NAMES:
            return
        data = event.get("data")
        if not isinstance(data, dict):
            return
        step = data.get("step")
        if not isinstance(step, str) or not step:
            override_step = self._THOUGHT_EVENT_STEP_OVERRIDES.get(event_name)
            if not override_step:
                return
            data["step"] = override_step
            step = override_step
        counter = self._thought_counters.get(step, 0) + 1
        self._thought_counters[step] = counter
        data.setdefault("thought_id", f"{step}:{counter}")
        text_key: Optional[str] = None
        text_value: Optional[str] = None
        for candidate in ("message", "thinking"):
            value = data.get(candidate)
            if isinstance(value, str):
                text_key = candidate
                text_value = value
                break
        if text_key:
            previous_value = self._last_thoughts.get(step, "")
            delta_text = text_value or ""
            if previous_value and delta_text.startswith(previous_value):
                delta_text = delta_text[len(previous_value) :]
            if delta_text and delta_text.startswith("\n"):
                delta_text = delta_text.lstrip("\n")
            if not previous_value and not delta_text and text_value:
                delta_text = text_value
            if delta_text:
                data[text_key] = delta_text
            else:
                data.pop(text_key, None)
            data["delta_text"] = delta_text or ""
            if text_value:
                self._last_thoughts[step] = text_value
            elif step in self._last_thoughts:
                self._last_thoughts.pop(step, None)
        else:
            self._last_thoughts.pop(step, None)

    def _maybe_reset_thought_cache(self, event: Dict[str, Any]) -> None:
        event_name = event.get("event")
        step: Optional[str] = None
        if event_name == "complete":
            data = event.get("data")
            if isinstance(data, dict):
                candidate = data.get("step")
                if isinstance(candidate, str) and candidate:
                    step = candidate
        else:
            step = self._THOUGHT_COMPLETION_EVENTS.get(event_name)
        if isinstance(step, str) and step:
            self._last_thoughts.pop(step, None)

    def _annotate(self, event: Dict[str, Any]) -> Dict[str, Any]:
        annotated = apply_mode_metadata(event, self.flow_mode)
        data = annotated.setdefault("data", {})
        data.setdefault("follow_up_route", self.follow_up_route.value)
        if isinstance(data, dict):
            data.setdefault("prompt_versions", dict(self._prompt_versions))
        self._attach_thought_metadata(annotated)
        self._maybe_reset_thought_cache(annotated)
        return annotated

    async def events(
        self,
        query: str,
        session_id: Optional[str] = None,
        *,
        hooks: Optional[AnalyticsFlowHooks] = None,
        revision_requested: bool = False,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self._thought_counters.clear()
        self._last_thoughts.clear()
        stream = self._pipeline.events(query, session_id, revision_requested=revision_requested)
        if hooks is None:
            async for event in stream:
                yield self._annotate(event)
            return

        hook_ctx: Dict[str, Any] = {"query": query, "session_id": session_id}
        try:
            async for start_event in hooks.on_flow_start(hook_ctx):
                yield self._annotate(start_event)
            async for event in stream:
                async for pre_event in hooks.before_event(hook_ctx, event):
                    yield self._annotate(pre_event)
                annotated = self._annotate(event)
                yield annotated
                if event.get("event") == "session_started":
                    data = event.get("data") or {}
                    hook_ctx["session_id"] = data.get("session_id", hook_ctx.get("session_id"))
                async for post_event in hooks.after_event(hook_ctx, event):
                    yield self._annotate(post_event)
        except BaseException as exc:
            async for end_event in hooks.on_flow_end(hook_ctx, error=exc):
                yield self._annotate(end_event)
            raise
        else:
            async for end_event in hooks.on_flow_end(hook_ctx):
                yield self._annotate(end_event)
# Standalone wrapper function for main.py
async def run_planner_executor(
    query: str,
    session_id: Optional[str] = None,
    *,
    revision_requested: bool = False,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Helper to stream planner-executor events without referencing the registry."""
    workflow_instance = PlannerExecutorFlow()
    async for event in workflow_instance.events(query, session_id, revision_requested=revision_requested):
        yield event








