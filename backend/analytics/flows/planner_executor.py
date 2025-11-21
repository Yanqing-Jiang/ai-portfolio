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
# Function: _safe_year
#   Role: Handles safe year logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating safe year behavior across flows.
# Function: _safe_date
#   Role: Handles safe date logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating safe date behavior across flows.
# Function: _summarize_sql_rows
#   Role: Handles summarize sql rows logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.flows.planner_executor._safe_year, analytics.flows.planner_executor._safe_date
#   Why: Keeps analytics.flows.planner_executor from duplicating summarize sql rows behavior across flows.
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
# Function: _build_schema_clarifier_request
#   Role: Handles build schema clarifier request logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.core.types.ClarifyRequestModel, uuid.uuid4
#   Why: Keeps analytics.flows.planner_executor from duplicating build schema clarifier request behavior across flows.
# Function: _followup_to_clarify_request
#   Role: Handles followup to clarify request logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.core.types.ClarifyRequestModel, uuid.uuid4
#   Why: Keeps analytics.flows.planner_executor from duplicating followup to clarify request behavior across flows.
# Function: _compose_intent_from_resolution
#   Role: Merge structured slot resolution output with heuristic signals into a runtime IntentModel.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.core.intent.detect_intent, analytics.core.intent.post_process_slots, analytics.core.types.IntentModel
#   Why: Supports downstream analytics workflows that rely on _compose_intent_from_resolution.
# Function: _normalize_metric_slots
#   Role: Handles normalize metric slots logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating normalize metric slots behavior across flows.
# Function: _build_slot_assumptions
#   Role: Handles build slot assumptions logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating build slot assumptions behavior across flows.
# Function: _apply_plan_metric_defaults
#   Role: Ensure metric slots are populated when the query plan already specifies concrete metrics.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.core.intent_impl.normalization.normalize_metrics, analytics.core.margins.detect_margin_choice_from_metrics, analytics.core.intent_impl.models.SlotStatusModel
#   Why: Returns the normalized metric list that was applied, or an empty list if no updates occurred.
# Function: _request_allows_custom
#   Role: Handles request allows custom logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating request allows custom behavior across flows.
# Function: _clarify_request_to_followup
#   Role: Handles clarify request to followup logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.flows.planner_executor._request_allows_custom, analytics.core.intent_impl.models.FollowUpModel
#   Why: Keeps analytics.flows.planner_executor from duplicating clarify request to followup behavior across flows.
# Function: _upsert_slot_status
#   Role: Handles upsert slot status logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.core.intent_impl.models.SlotStatusModel, analytics.core.intent_impl.normalization.normalize_timeframe, analytics.core.intent_impl.normalization.normalize_metrics
#   Why: Keeps analytics.flows.planner_executor from duplicating upsert slot status behavior across flows.
# Function: _refresh_followups
#   Role: Handles refresh followups logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.flows.planner_executor._clarify_request_to_followup
#   Why: Keeps analytics.flows.planner_executor from duplicating refresh followups behavior across flows.
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
#   Invokes: time.time, analytics.flows.planner_executor._normalize_metric_slots, analytics.flows.planner_executor._build_slot_assumptions, analytics.flows.planner_executor._compose_intent_from_resolution, +2 more
#   Why: Keeps analytics.flows.planner_executor from duplicating intent phase behavior across flows.
# Function: _clarification_phase
#   Role: Handles clarification phase logic for analytics.flows.planner_executor.
#   Called from: Internal to analytics.flows.planner_executor
#   Invokes: analytics.flows.planner_executor._refresh_followups, analytics.flows.planner_executor._auto_fill_missing_slots, analytics.artifacts.ClarificationArtifact, analytics.core.clarify.validate_clarification_answer, +2 more
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
# Function: _auto_fill_missing_slots
#   Role: Handles auto fill missing slots logic for analytics.flows.planner_executor.
#   Called from: tests.analytics.test_clarification_auto_fill, tests.analytics.test_planner_executor_sql
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner_executor from duplicating auto fill missing slots behavior across flows.
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
from analytics.core.session_state import (
    SnapshotRevisionContext,
    SessionStateSnapshot,
    digest_tool_payload,
    get_session_state_repository,
    normalize_row_count,
)
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
from analytics.routing import FollowUpRoute
from analytics.validators import sanitize_for_json

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
from analytics.sql.validator import validate_sql
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
    compose_chart_ready_payload,
    compose_sql_ready_payload,
    compose_stock_ready_payload,
    compose_web_ready_payload,
    limit_sample_rows,
    derive_accessory_events,
    ensure_analysis_dependencies,
    annotate_revision_event,
    build_revision_request_event,
    build_revision_plan,
    apply_revision_plan,
    derive_revision_targets,
    normalize_revision_targets,
    start_tool_parallelism,
    stream_analysis_lane,
    stream_chart_lane,
    stream_sql_lane,
)
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
from analytics.core.clarify import (
    detect_missing_slots,
    merge_answers,
    wait_for_answer_blocking,
    compute_required_clarifications,
    validate_clarification_answer,
    get_validation_error_message,
)
from unified_responses_client import get_unified_client
CONFIGS = get_configs()
CONFIG_STORE = get_config_store()
SUPERVISOR_TOOLS = SupervisorTools()
logger = logging.getLogger(__name__)

_TOOL_TO_ANALYSIS_LANE: Dict[str, str] = {
    "sql_generator": "sql",
    "sql_generation": "sql",
    "sql_executor": "sql",
    "sql_execution": "sql",
    "sql_planner": "sql",
    "chart_designer": "chart",
    "chart_builder": "chart",
    "chart_generation": "chart",
    "stock_tracker": "stock",
    "market_question_a": "stock",
    "market_question_b": "stock",
    "market_research": "stock",
    "web_retriever": "web",
    "web_retriever_cached": "web",
    "web_retriever_live": "web",
    "web_research": "web",
}

_FLOW_MODE_TO_RESOLVER_MODE: Dict[FlowMode, str] = {
    FlowMode.DIRECT: "single_agent",
    FlowMode.SINGLE_AGENT: "fanout",
    FlowMode.MULTI_AGENT: "multi_agent",
}

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

# Schema clarifier is now always enabled (legacy env flag removed)
SCHEMA_CLARIFIER_ENABLED = True

def _generate_chart_design(intent_key: Optional[str], plan: QueryPlanModel, data: List[Dict[str, Any]], spec: Dict[str, Any]) -> Dict[str, Any]:
    """Generate smart chart design metadata for frontend optimization."""
    if not intent_key or not data:
        return {}
    # Extract available columns from data
    cols = list(data[0].keys()) if data else []
    has_multiple_tickers = len(set(row.get('ticker') for row in data if row.get('ticker'))) > 1
    comparison = getattr(plan, "comparison", None)
    design = {
        'intent': intent_key,
        'grouping': 'ticker' if has_multiple_tickers else 'metric',
        'chart_type': 'line_multi',
        'y_axis': {'type': 'dual'},
        'legend_order': [],
        'defaultLegendSelection': {},
        'color_by': 'ticker' if has_multiple_tickers else 'metric'
    }
    if comparison:
        design['comparison'] = comparison
        if comparison == 'all' and has_multiple_tickers:
            design['comparison_mode'] = 'multi_company'
    if getattr(plan, "statistic", None) == "ranking_latest":
        primary_metric = (plan.metrics or [None])[0]
        design.update({
            'chart_type': 'ranking_bar',
            'grouping': 'ticker',
            'y_axis': {'type': 'single'},
            'measure': primary_metric,
            'statistic': plan.statistic,
        })
    # Intent-specific configurations
    if intent_key == 'market_share_all':
        design.update({
            'chart_type': 'stacked_area_100',
            'measure': 'market_share_percent',
            'top_n': 3,
            'aggregate_rest': True,
            'rest_label': 'Others',
            'y_axis': {'type': 'percent_only'}
        })
    elif intent_key == 'market_share_single':
        design.update({
            'measure': 'market_share_percent',
            'y_axis': {'type': 'dual'},  # market share + revenue context
            'defaultLegendSelection': {'market_share_percent': True}
        })
    elif intent_key in ['revenue_growth_analysis']:
        design.update({
            'measure': ['qoq_growth_percent', 'yoy_growth_percent'],
            'y_axis': {'type': 'dual'},  # growth on right, revenue context on left
            'defaultLegendSelection': {
                'qoq_growth_percent': True, 
                'yoy_growth_percent': True,
                'quarterly_revenue': False  # context series hidden by default
            }
        })
    elif intent_key in ['margins_vs_peers', 'margin_growth_vs_peers']:
        choice = detect_margin_choice_from_plan(plan)
        if choice:
            if intent_key == 'margins_vs_peers':
                measures = [choice.value_alias, choice.peer_alias]
            else:
                measures = [choice.growth_alias, choice.growth_peer_alias]
            default_selection = {alias: True for alias in measures}
        else:
            if intent_key == 'margins_vs_peers':
                measures = ['gross_margin', 'operating_margin', 'net_margin']
                default_selection = {'operating_margin': True, 'net_margin': True}
            else:
                measures = [
                    'company_gross_margin_change_pp',
                    'company_operating_margin_change_pp',
                    'company_net_margin_change_pp',
                    'peer_avg_gross_margin_change_pp',
                    'peer_avg_operating_margin_change_pp',
                    'peer_avg_net_margin_change_pp',
                ]
                default_selection = {
                    'company_operating_margin_change_pp': True,
                    'company_net_margin_change_pp': True,
                }
        design.update({
            'measure': measures,
            'y_axis': {'type': 'percent_only'},
            'defaultLegendSelection': default_selection,
        })
    elif intent_key in ['rnd_intensity_vs_peers', 'rnd_expense_vs_peers']:
        design.update({
            'measure': 'company_rnd_intensity' if 'intensity' in intent_key else 'company_rnd_expense',
            'y_axis': {'type': 'percent_only'} if 'intensity' in intent_key else {'type': 'currency_only'},
            'chart_type': 'line_multi'
        })
    return design

def _validate_sql(sql: str) -> Tuple[bool, List[str], int]:
    start = time.time()
    ok, issues = validate_sql(sql)
    elapsed = int((time.time() - start) * 1000)
    return ok, issues, elapsed


@dataclass
class ToolInvocationReceipt:
    tool: str
    status: str
    attempts: int = 0
    elapsed_ms: Optional[int] = None
    latency_ms: Optional[int] = None
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    reused: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source_lane: Optional[str] = None
    reused_at_ms: Optional[int] = None
    arguments_digest: Optional[str] = None
    output_digest: Optional[str] = None
    latency_guardrail: Optional[Dict[str, Any]] = None
    guardrail: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.latency_ms is None and self.elapsed_ms is not None:
            self.latency_ms = self.elapsed_ms

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "tool": self.tool,
            "status": self.status,
            "attempts": self.attempts,
            "elapsed_ms": self.elapsed_ms,
            "latency_ms": self.latency_ms,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "reused": self.reused,
            "error": self.error,
            "timestamp": self.timestamp,
            "source_lane": self.source_lane,
            "reused_at_ms": self.reused_at_ms,
        }
        if self.metadata:
            payload["metadata"] = sanitize_for_json(self.metadata)
        if self.arguments_digest:
            payload["arguments_digest"] = self.arguments_digest
        if self.output_digest:
            payload["output_digest"] = self.output_digest
        if self.latency_guardrail:
            payload["latency_guardrail"] = sanitize_for_json(self.latency_guardrail)
        if self.guardrail:
            payload["guardrail"] = sanitize_for_json(self.guardrail)
        return {key: value for key, value in payload.items() if value is not None}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToolInvocationReceipt":
        metadata = payload.get("metadata") or {}
        latency_candidate = payload.get("latency_ms")
        if latency_candidate is None:
            latency_candidate = payload.get("elapsed_ms")
        latency_ms: Optional[int]
        try:
            latency_ms = int(latency_candidate) if latency_candidate is not None else None
        except (TypeError, ValueError):
            latency_ms = None
        reused_at_candidate = payload.get("reused_at_ms")
        if reused_at_candidate is None:
            reused_at_candidate = payload.get("fast_path_latency_ms")
        try:
            reused_at_ms = int(reused_at_candidate) if reused_at_candidate is not None else None
        except (TypeError, ValueError):
            reused_at_ms = None
        arguments_digest = payload.get("arguments_digest")
        if arguments_digest is not None:
            arguments_digest = str(arguments_digest)
        output_digest = payload.get("output_digest")
        if output_digest is not None:
            output_digest = str(output_digest)
        latency_guardrail = payload.get("latency_guardrail")
        if isinstance(latency_guardrail, Mapping):
            latency_guardrail = sanitize_for_json(latency_guardrail)
        else:
            latency_guardrail = None
        guardrail_payload = payload.get("guardrail")
        if isinstance(guardrail_payload, Mapping):
            guardrail_payload = sanitize_for_json(guardrail_payload)
        else:
            guardrail_payload = None
        return cls(
            tool=str(payload.get("tool") or ""),
            status=str(payload.get("status") or "unknown"),
            attempts=int(payload.get("attempts") or 0),
            elapsed_ms=payload.get("elapsed_ms"),
            latency_ms=latency_ms,
            input_hash=payload.get("input_hash"),
            output_hash=payload.get("output_hash"),
            reused=bool(payload.get("reused", False)),
            error=payload.get("error"),
            metadata=dict(metadata) if isinstance(metadata, Mapping) else {},
            timestamp=str(payload.get("timestamp") or datetime.utcnow().isoformat()),
            source_lane=payload.get("source_lane") or payload.get("lane"),
            reused_at_ms=reused_at_ms,
            arguments_digest=arguments_digest,
            output_digest=output_digest,
            latency_guardrail=latency_guardrail,
            guardrail=guardrail_payload,
        )


@dataclass
class PlannerRevisionContext:
    session_id: str
    receipts: Dict[str, ToolInvocationReceipt] = field(default_factory=dict)
    lane_refresh_overrides: Dict[str, bool] = field(default_factory=dict)
    lane_ttls: Dict[str, int] = field(default_factory=dict)
    lane_timestamps: Dict[str, datetime] = field(default_factory=dict)
    reasoning_summaries: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    accessories: Dict[str, Any] = field(default_factory=dict)
    last_analysis: Optional[str] = None
    last_chart_spec: Optional[Dict[str, Any]] = None
    snapshot_payload: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_snapshot(
        cls,
        snapshot: Optional[SessionStateSnapshot],
        *,
        lane_refresh_overrides: Mapping[str, bool],
    ) -> Optional["PlannerRevisionContext"]:
        if snapshot is None:
            return None
        snapshot_ctx: SnapshotRevisionContext = snapshot.revision_context()
        lane_ttls = dict(snapshot_ctx.lane_ttls) if snapshot_ctx.lane_ttls else resolve_lane_ttls()
        receipts: Dict[str, ToolInvocationReceipt] = {}
        for tool_name, payload in snapshot_ctx.tool_receipts.items():
            try:
                receipts[tool_name] = ToolInvocationReceipt.from_dict(payload)
            except Exception:
                continue
        normalized_overrides: Dict[str, bool] = {}
        for lane, required in (lane_refresh_overrides or {}).items():
            key = cls._normalize_lane(lane)
            if key:
                normalized_overrides[key] = bool(required)
        accessories: Dict[str, Any] = {}
        snapshot_payload: Dict[str, Any] = {}
        revision_snapshot = snapshot_ctx.revision_snapshot or {}
        if isinstance(revision_snapshot, Mapping):
            snapshot_payload = copy.deepcopy(revision_snapshot)
            web_snapshot = revision_snapshot.get("web_context")
            if isinstance(web_snapshot, Mapping):
                accessories["web"] = copy.deepcopy(web_snapshot)
            stock_snapshot = revision_snapshot.get("stock_widget")
            if stock_snapshot is not None:
                accessories["market"] = copy.deepcopy(stock_snapshot)
        return cls(
            session_id=snapshot_ctx.session_id,
            receipts=receipts,
            lane_refresh_overrides=normalized_overrides,
            lane_ttls=lane_ttls,
            lane_timestamps=dict(snapshot_ctx.lane_timestamps),
            reasoning_summaries=copy.deepcopy(snapshot_ctx.agent_reasoning),
            accessories=accessories,
            last_analysis=snapshot_ctx.last_analysis,
            last_chart_spec=copy.deepcopy(snapshot_ctx.last_chart_spec) if snapshot_ctx.last_chart_spec else None,
            snapshot_payload=snapshot_payload,
        )

    @staticmethod
    def _normalize_lane(lane: Optional[str]) -> Optional[str]:
        if lane is None:
            return None
        normalized = str(lane).strip().lower()
        return normalized or None

    def lane_age_seconds(self, lane: str, *, now: Optional[datetime] = None) -> Optional[float]:
        normalized = self._normalize_lane(lane)
        if not normalized:
            return None
        timestamp = self.lane_timestamps.get(normalized)
        if timestamp is None:
            return None
        now_dt = now or datetime.now(timezone.utc)
        try:
            delta = now_dt - timestamp
            return max(delta.total_seconds(), 0.0)
        except Exception:
            return None

    def should_refresh(self, lane: str) -> bool:
        normalized = self._normalize_lane(lane)
        if not normalized:
            return True
        if normalized in self.lane_refresh_overrides:
            return self.lane_refresh_overrides[normalized]
        ttl = self.lane_ttls.get(normalized)
        if ttl is None or ttl <= 0:
            return True
        age = self.lane_age_seconds(normalized)
        if age is None:
            return True
        return age > ttl

    def accessory_snapshot(self, lane: str) -> Optional[Dict[str, Any]]:
        normalized = self._normalize_lane(lane)
        if not normalized:
            return None
        payload = self.accessories.get(normalized)
        if payload is None:
            return None
        return copy.deepcopy(payload)


def _hash_payload(payload: Any) -> str:
    try:
        normalized = sanitize_for_json(payload)
    except Exception:
        normalized = payload
    try:
        encoded = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    except TypeError:
        encoded = json.dumps(str(normalized), sort_keys=True).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()


def _accessory_tool_adapters() -> Tuple[Any, ...]:
    """Return tool adapters that supply market and web lanes."""
    return (
        MarketQuestionAdapter("market_question_a", "Market Research Question A"),
        MarketQuestionAdapter("market_question_b", "Market Research Question B"),
        StockTrackerAdapter(),
        WebRetrieverAdapter(),
    )


@dataclass
class PlannerPhaseContext:
    query: str
    session_id: str
    workflow_start: float
    timed_emitter: TimedEventEmitter
    flow_mode: FlowMode = FlowMode.DIRECT
    configs: Dict[str, Any] = field(default_factory=dict)
    classification: Optional[OffTopicClassifierSchema] = None
    is_financial_query: bool = True
    intent: Optional[IntentModel] = None
    provisional_plan: Optional[QueryPlanModel] = None
    template: Optional[Any] = None
    clarifications: List[ClarifyRequestModel] = field(default_factory=list)
    clarification_sources: Set[str] = field(default_factory=set)
    assumptions: List[str] = field(default_factory=list)
    intent_resolution: Optional[IntentResolutionModel] = None
    slot_statuses: Dict[str, SlotStatusModel] = field(default_factory=dict)
    slot_followups: List[FollowUpModel] = field(default_factory=list)
    clarification_rounds: int = 0
    clarifier_agent_invoked: bool = False
    schema_clarifier_decision: Optional[ClarifierDecision] = None
    plan: Optional[QueryPlanModel] = None
    candidate_templates: List[Dict[str, Any]] = field(default_factory=list)
    selected_template_id: Optional[str] = None
    web_search: Optional[ResponseSearchResult] = None
    web_search_seeded: bool = False
    stock_widget_seeded: bool = False
    parallelism_enabled: bool = False
    follow_up_route: FollowUpRoute = FollowUpRoute.FULL_PIPELINE
    reuse_sql: bool = False
    stock_only: bool = False
    artifacts: PipelineArtifacts = field(default_factory=PipelineArtifacts)
    snapshot_artifacts: Optional[PipelineArtifacts] = None
    revision_snapshot: Optional[Dict[str, Any]] = None
    prior_intent_signature: Optional[Dict[str, Any]] = None
    intent_signature: Optional[Dict[str, Any]] = None
    criteria_changed: bool = False
    reuse_snapshot_active: bool = False
    reused_sql: bool = False
    reused_chart: bool = False
    reused_stock: bool = False
    reused_web: bool = False
    reused_analysis: bool = False
    snapshot_age_seconds: Optional[float] = None
    snapshot_stale: bool = False
    tool_receipts: Dict[str, ToolInvocationReceipt] = field(default_factory=dict)
    revision_targets: Set[str] = field(default_factory=set)
    revision_id: Optional[str] = None
    revision_hint_active: bool = False
    revision_directive: Optional["RevisionDirective"] = None
    agentic_revision_mode: bool = False
    force_full_fresh_pipeline: bool = False
    halted: bool = False
    halt_reason: Optional[str] = None
    lane_refresh_required: Dict[str, bool] = field(default_factory=dict)
    analysis_refresh_mode: str = "full"
    session_follow_up: bool = False
    revision_context: Optional[PlannerRevisionContext] = None
    revision_reasoning: Dict[str, Dict[str, Any]] = field(default_factory=dict)

AGGREGATE_METRIC_MARKERS = (
    "'r&d expense'",
    "'revenue'",
    "'operating cash flow'",
    "'capex'",
    "'capital expenditures'",
    "'operating income'",
    "'net income'",
)

SQL_DATASET_PREVIEW_LIMIT = 200
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_DEFAULT_GUARDRAIL_P50 = int(os.getenv("WEB_SEARCH_GUARDRAIL_P50_MS", "1200"))
_DEFAULT_GUARDRAIL_P95 = int(os.getenv("WEB_SEARCH_GUARDRAIL_P95_MS", "2500"))
_RISK_TERMS = (
    "risk",
    "headwind",
    "concern",
    "pressure",
    "downside",
    "volatility",
    "slowdown",
    "uncertain",
    "watchlist",
    "caution",
)
_ACTION_TERMS = (
    "consider",
    "monitor",
    "focus",
    "plan to",
    "plan for",
    "watch",
    "track",
    "follow up",
    "prepare",
    "should",
    "next step",
    "next steps",
    "keep an eye",
)
_NUMERIC_HINTS = ("%", "bps", "basis point", "million", "billion", "m$", "bn")
SNAPSHOT_MAX_AGE_SECONDS = int(os.getenv("ANALYTICS_SNAPSHOT_MAX_AGE_SECONDS", "600"))
_WEB_TOOL_NAMES = {"web_retriever", "web_retriever_cached", "web_retriever_live"}
_MARKET_TOOL_NAMES = {"stock_tracker", "market_question_a", "market_question_b"}
FRESH_RUN_REASONING_EFFORT = "minimal"
CLASSIFIER_TIMEOUT_SECONDS = float(os.getenv("ANALYTICS_CLASSIFIER_TIMEOUT_SECONDS", "2.5"))

FOLLOW_UP_BANNERS: Dict[FollowUpRoute, Dict[str, str]] = {
    FollowUpRoute.FULL_PIPELINE: {
        "title": "Fresh Run Scheduled",
        "message": "Running SQL, charts, and narrative again to deliver a fully refreshed answer.",
    },
    FollowUpRoute.REUSE_SQL: {
        "title": "Reusing Last Dataset",
        "message": "Skipping the SQL rerun - updating visuals and narrative on top of the validated table.",
    },
    FollowUpRoute.STOCK_ONLY: {
        "title": "Market Snapshot Only",
        "message": "Pulling fresh price data while charts and analysis stay pinned to the prior run.",
    },
}


def _normalize_calendar_filters(sql: str) -> str:
    if not sql:
        return sql
    lower_sql = sql.lower()
    if "calendar_quarter_num is null" not in lower_sql:
        return sql
    if "sum(" not in lower_sql:
        return sql
    if not any(marker in lower_sql for marker in AGGREGATE_METRIC_MARKERS):
        return sql
    return re.sub(r"calendar_quarter_num\s+IS\s+NULL", "calendar_quarter_num IS NOT NULL", sql, flags=re.IGNORECASE)


def _safe_year(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit() and len(stripped) <= 4:
            return int(stripped)
    return None


def _safe_date(value: Any) -> Optional[date]:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        cleaned = stripped.rstrip("Z")
        try:
            return datetime.fromisoformat(cleaned).date()
        except ValueError:
            return None
    return None


def _summarize_sql_rows(data: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    if not isinstance(data, list):
        data = []
    columns: List[str] = sorted({key for row in data if isinstance(row, dict) for key in row.keys()})
    sample_rows: List[Dict[str, Any]] = []
    for row in data[:5]:
        if isinstance(row, dict):
            sample_rows.append({column: row.get(column) for column in columns})
    tickers = sorted(
        {
            str(row.get("ticker")).strip()
            for row in data
            if isinstance(row, dict) and row.get("ticker")
        }
    )
    metric_keys = ("metric", "metric_name", "series", "measure", "line_item")
    metrics = sorted(
        {
            str(row.get(key)).strip()
            for row in data
            if isinstance(row, dict)
            for key in metric_keys
            if row.get(key)
        }
    )
    years: List[int] = []
    dates: List[date] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        for key, value in row.items():
            lower = key.lower()
            if "year" in lower:
                maybe_year = _safe_year(value)
                if maybe_year is not None:
                    years.append(maybe_year)
            if "date" in lower or "period" in lower:
                maybe_date = _safe_date(value)
                if maybe_date is not None:
                    dates.append(maybe_date)
    timeframe: Dict[str, Any] = {}
    if years:
        timeframe["years"] = {"min": min(years), "max": max(years)}
    if dates:
        timeframe["dates"] = {
            "start": min(dates).isoformat(),
            "end": max(dates).isoformat(),
        }
    return {
        "columns": columns,
        "sample_rows": sample_rows,
        "tickers": tickers,
        "metrics": metrics,
        "timeframe": timeframe,
    }


def _build_classifier_fallback(reason: str) -> OffTopicClassifierSchema:
    logger.warning("Classifier fallback engaged: %s", reason)
    polite_message = (
        "I'm focused on financial analytics questions. Please include a company, ticker, or metric if you need help."
    )
    return OffTopicClassifierSchema(
        is_financial_query=True,
        confidence=0.55,
        topic_category="financial_analytics",
        polite_decline_message=None,
        suggested_rephrase=polite_message,
    )


async def _run_classifier_with_timeout(
    ctx: "PlannerPhaseContext",
    model_name: str,
    provider: Optional[str],
) -> OffTopicClassifierSchema:
    try:
        return await asyncio.wait_for(
            classify_query_async(
                ctx.query,
                session_id=ctx.session_id,
                model=model_name,
                reasoning_effort="low",
                provider=provider,
            ),
            timeout=CLASSIFIER_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "[CLASSIFICATION] Model timeout after %.2fs (session=%s)",
            CLASSIFIER_TIMEOUT_SECONDS,
            ctx.session_id,
        )
        return _build_classifier_fallback("timeout")
    except Exception as exc:
        logger.exception("[CLASSIFICATION] Model error; using fallback: %s", exc)
        return _build_classifier_fallback(str(exc))


def _set_sql_generation_artifact(
    ctx: PlannerPhaseContext,
    *,
    sql: Optional[str],
    template_id: Optional[str],
    attempts: Sequence[Dict[str, Any]],
    llm_used: bool,
    last_error_code: Optional[str],
    last_error_detail: Optional[str],
    status: str,
) -> None:
    ctx.artifacts.sql_generation = SQLGenerationArtifact(
        query=ctx.query,
        sql=sql,
        template_id=template_id,
        attempts=list(attempts),
        llm_used=llm_used,
        last_error=last_error_detail,
        last_error_code=last_error_code,
        last_error_detail=last_error_detail,
        status=status,
    )


def _set_sql_execution_artifact(
    ctx: PlannerPhaseContext,
    *,
    data: Optional[List[Dict[str, Any]]],
    elapsed_ms: Optional[int],
    status: str,
    error: Optional[str] = None,
    error_code: Optional[str] = None,
) -> None:
    dataset: List[Dict[str, Any]] = list(data or [])
    summary = _summarize_sql_rows(dataset)
    row_count = len(dataset) if dataset else None
    dataset_preview = dataset[:SQL_DATASET_PREVIEW_LIMIT] if dataset else []
    ctx.artifacts.sql_execution = SQLExecutionArtifact(
        query=ctx.query,
        row_count=row_count,
        columns=summary["columns"],
        tickers=summary["tickers"],
        metrics=summary["metrics"],
        timeframe=summary["timeframe"],
        sample_rows=summary["sample_rows"],
        dataset_preview=dataset_preview,
        dataset=dataset,
        elapsed_ms=elapsed_ms,
        status=status,
        error=error,
        error_code=error_code,
    )


def _summarize_chart_series(plan: Any, spec: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    series_summary: List[Dict[str, Any]] = []
    plan_dict: Dict[str, Any] = {}
    if hasattr(plan, "dict"):
        try:
            plan_dict = plan.dict()
        except Exception:
            plan_dict = {}
    elif isinstance(plan, dict):
        plan_dict = dict(plan)
    for entry in plan_dict.get("series", []) or []:
        if isinstance(entry, dict):
            summary = {
                key: entry.get(key)
                for key in ("id", "metric", "measure", "comparison", "axis")
                if entry.get(key) is not None
            }
            if summary:
                series_summary.append(summary)
    # Fallback to spec datasets if series empty
    if not series_summary and isinstance(spec, dict):
        datasets = spec.get("datasets")
        if isinstance(datasets, list):
            for dataset in datasets:
                if isinstance(dataset, dict):
                    label = dataset.get("label") or dataset.get("name")
                    series_summary.append(
                        {
                            "label": label,
                            "id": dataset.get("id"),
                            "metric": dataset.get("metric"),
                        }
                    )
    return series_summary


def _get_sql_dataset(ctx: PlannerPhaseContext) -> List[Dict[str, Any]]:
    execution_artifact = getattr(ctx.artifacts, "sql_execution", None)
    if execution_artifact is None:
        return []
    dataset = getattr(execution_artifact, "dataset", None) or []
    if dataset:
        return list(dataset)
    preview = getattr(execution_artifact, "dataset_preview", None) or []
    if preview:
        return list(preview)
    return list(execution_artifact.sample_rows)


def _extract_tldr(text: str) -> Optional[str]:
    stripped = (text or "").strip()
    if not stripped:
        return None
    first_paragraph = stripped.split("\n\n", 1)[0].strip()
    first_sentence = first_paragraph.split(". ", 1)[0].strip()
    return first_sentence[:240] if first_sentence else None


def _extract_bullets(text: str, limit: int = 3) -> List[str]:
    bullets: List[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped[0] in {"-", "*", "\u2022"}:
            content = stripped.lstrip("-* \u2022").strip()
            if content:
                bullets.append(content)
        if len(bullets) >= limit:
            break
    return bullets


def _split_line(line: str) -> List[str]:
    stripped = line.strip()
    if not stripped:
        return []
    if stripped[0] in {"-", "*", "\u2022"}:
        cleaned = stripped.lstrip("-*\u2022 ").strip()
        return [cleaned] if cleaned else []
    return _SENTENCE_SPLIT.split(stripped)


def _normalize_sentence(sentence: str) -> Optional[str]:
    cleaned = re.sub(r"\s+", " ", sentence or "").strip()
    return cleaned or None


def _collect_sentences(text: str) -> List[str]:
    sentences: List[str] = []
    seen: set[str] = set()
    for raw_line in (text or "").splitlines():
        for fragment in _split_line(raw_line):
            normalized = _normalize_sentence(fragment)
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            sentences.append(normalized)
    return sentences


def _extract_key_numbers(text: str, limit: int = 3) -> List[str]:
    sentences = _collect_sentences(text)
    key_numbers: List[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        has_numeric = any(char.isdigit() for char in sentence)
        if not has_numeric and not any(hint in lowered for hint in _NUMERIC_HINTS):
            continue
        key_numbers.append(sentence[:240])
        if len(key_numbers) >= limit:
            break
    return key_numbers


def _extract_risk_watch(text: str, limit: int = 2) -> List[str]:
    sentences = _collect_sentences(text)
    risks: List[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(term in lowered for term in _RISK_TERMS):
            risks.append(sentence[:240])
        if len(risks) >= limit:
            break
    return risks


def _extract_next_steps(text: str, limit: int = 2) -> List[str]:
    sentences = _collect_sentences(text)
    next_steps: List[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(term in lowered for term in _ACTION_TERMS):
            next_steps.append(sentence[:240])
        if len(next_steps) >= limit:
            break
    return next_steps


def _build_evidence_entries(
    *,
    web_context: Optional[Dict[str, Any]],
    highlights: Optional[List[str]],
    summary: Optional[str],
    max_items: int = 5,
) -> List[Dict[str, Any]]:
    if not web_context or not isinstance(web_context, dict):
        return []

    snippets = web_context.get("snippets") or []
    if not isinstance(snippets, list):
        return []

    claims: List[str] = []
    if summary:
        claims.append(summary)
    if highlights:
        claims.extend(highlights)

    evidence: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()

    for index, raw_snippet in enumerate(snippets):
        if not isinstance(raw_snippet, dict):
            continue
        url = raw_snippet.get("url") or raw_snippet.get("source_url")
        if not isinstance(url, str) or not url.strip():
            continue
        normalized_url = url.strip()
        if normalized_url in seen_urls:
            continue
        title = raw_snippet.get("title") or raw_snippet.get("display_url")
        snippet_text = raw_snippet.get("snippet") or raw_snippet.get("summary")

        entry: Dict[str, Any] = {
            "source_url": normalized_url,
        }
        if isinstance(title, str) and title.strip():
            entry["title"] = title.strip()
        display_url = raw_snippet.get("display_url")
        if isinstance(display_url, str) and display_url.strip():
            entry["display_url"] = display_url.strip()
        if isinstance(snippet_text, str) and snippet_text.strip():
            excerpt = snippet_text.strip()
            if len(excerpt) > 260:
                excerpt = excerpt[:257].rstrip() + "..."
            entry["snippet"] = excerpt
        published_at = raw_snippet.get("published_at")
        if isinstance(published_at, str) and published_at.strip():
            entry["published_at"] = published_at.strip()
        if claims:
            claim_idx = index if index < len(claims) else -1
            if claim_idx >= 0:
                entry["claim"] = claims[claim_idx]
        annotation = raw_snippet.get("annotation") or {}
        confidence = annotation.get("confidence")
        if not isinstance(confidence, (int, float)):
            derived = 1.0 - (0.15 * index)
            confidence = max(0.1, round(derived, 2))
        else:
            confidence = round(max(0.0, min(float(confidence), 1.0)), 2)
        entry["confidence"] = confidence
        evidence.append(entry)
        seen_urls.add(normalized_url)
        if len(evidence) >= max_items:
            break

    return evidence


def _evaluate_latency_guardrail(
    stats: Optional[Dict[str, Any]],
    *,
    p50_threshold: Optional[int] = None,
    p95_threshold: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if not stats or not isinstance(stats, dict):
        return None

    observed_p50 = stats.get("p50_ms")
    observed_p95 = stats.get("p95_ms") or stats.get("max_ms")
    observed_total = stats.get("total_ms")
    thresholds = {
        "p50_ms": p50_threshold if p50_threshold is not None else _DEFAULT_GUARDRAIL_P50,
        "p95_ms": p95_threshold if p95_threshold is not None else _DEFAULT_GUARDRAIL_P95,
    }

    violations: List[str] = []
    if isinstance(observed_p50, (int, float)) and observed_p50 > thresholds["p50_ms"]:
        violations.append("p50_ms")
    if isinstance(observed_p95, (int, float)) and observed_p95 > thresholds["p95_ms"]:
        violations.append("p95_ms")

    status = "ok"
    if violations:
        status = "violation"

    guardrail_payload: Dict[str, Any] = {
        "status": status,
        "violations": violations,
        "observed": {
            key: stats.get(key)
            for key in ("total_ms", "p50_ms", "p95_ms", "max_ms", "samples")
            if stats.get(key) is not None
        },
        "thresholds": thresholds,
    }
    if observed_total is not None and guardrail_payload["observed"].get("total_ms") is None:
        guardrail_payload["observed"]["total_ms"] = observed_total
    return guardrail_payload


def _derive_scope_banner(ctx: PlannerPhaseContext, spec: Dict[str, Any]) -> Optional[str]:
    tickers: List[str] = []
    market_artifact = getattr(ctx.artifacts, "market", None)
    if market_artifact and market_artifact.tickers:
        tickers.extend(market_artifact.tickers)
    datasets = spec.get("datasets")
    if not tickers and isinstance(datasets, list):
        for dataset in datasets:
            if isinstance(dataset, dict):
                symbol = dataset.get("ticker") or dataset.get("symbol")
                if isinstance(symbol, str):
                    tickers.append(symbol)
    if not tickers:
        dataset_rows = _get_sql_dataset(ctx)
        for row in dataset_rows:
            symbol = row.get("ticker")
            if isinstance(symbol, str):
                tickers.append(symbol)
    deduped: List[str] = []
    for symbol in tickers:
        upper = symbol.strip().upper()
        if upper and upper not in deduped:
            deduped.append(upper)
    if not deduped:
        return None
    basis = ", ".join(deduped[:7])
    return f"Basis: Revenue share across {basis}"


def _set_chart_artifact(
    ctx: PlannerPhaseContext,
    *,
    spec: Dict[str, Any],
    chart_plan: Any,
    chart_design: Dict[str, Any],
) -> None:
    series_summary = _summarize_chart_series(chart_plan, spec)
    chart_type = getattr(chart_plan, "chart_type", None)
    try:
        serialized_spec = json.dumps(spec, sort_keys=True)
    except Exception:
        serialized_spec = repr(spec)
    spec_id = None
    try:
        spec_id = _make_identifier(ctx.session_id, "chart", serialized_spec)
        spec.setdefault("meta", {})["artifactSpecId"] = spec_id
    except Exception:
        spec_id = None
    scope_banner = _derive_scope_banner(ctx, spec)
    if scope_banner:
        spec.setdefault("meta", {})["scopeBanner"] = scope_banner
    ctx.artifacts.chart = ChartArtifact(
        query=ctx.query,
        spec=spec,
        spec_id=spec_id,
        design=chart_design or {},
        datasets_summary=series_summary,
        series_count=len(series_summary) if series_summary else None,
        chart_type=chart_type,
        scope_banner=scope_banner,
    )


def _set_market_artifact(
    ctx: PlannerPhaseContext,
    *,
    widget: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    error_code: Optional[str] = None,
) -> None:
    tickers: List[str] = []
    snapshot: Optional[Dict[str, Any]] = None
    if isinstance(widget, dict):
        snapshot = widget
        symbols = widget.get("symbols")
        if isinstance(symbols, list):
            tickers = [
                str(symbol).strip()
                for symbol in symbols
                if isinstance(symbol, str) and symbol.strip()
            ]
    ctx.artifacts.market = MarketArtifact(
        query=ctx.query,
        tickers=tickers,
        snapshot=snapshot,
        error=error,
        error_code=error_code,
    )


def _set_web_artifact(
    ctx: PlannerPhaseContext,
    *,
    payload: Dict[str, Any],
    topic: Optional[str],
    search_result: Optional[Any],
) -> None:
    metadata = {}
    if search_result is not None:
        metadata = dict(getattr(search_result, "metadata", {}) or {})
    ctx.artifacts.web = WebContextArtifact(
        query=ctx.query,
        summary=payload.get("summary"),
        snippets=list(payload.get("snippets") or []),
        search_id=payload.get("search_id"),
        from_cache=payload.get("from_cache"),
        metadata=metadata,
        topic=topic,
        latency_stats=payload.get("latency_stats"),
    )


class _PayloadSearchResultProxy:
    """Minimal wrapper so seeded payloads satisfy the ResponseSearchResult interface."""

    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = copy.deepcopy(payload)
        self.summary = self._payload.get("summary")
        self.latency_ms = self._payload.get("latency_ms")

    def to_payload(self) -> Dict[str, Any]:
        return copy.deepcopy(self._payload)


def _seed_web_search_from_payload(ctx: PlannerPhaseContext, payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        return
    sanitized_payload = sanitize_for_json(payload)
    ctx.web_search = _PayloadSearchResultProxy(sanitized_payload)
    ctx.web_search_seeded = True
    if sanitized_payload.get("from_cache"):
        ctx.reused_web = True
    topic = sanitized_payload.get("topic") or sanitized_payload.get("search_topic")
    _set_web_artifact(ctx, payload=sanitized_payload, topic=topic, search_result=None)


def _seed_stock_widget_from_payload(ctx: PlannerPhaseContext, payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        return
    widget_payload = payload.get("stock_widget")
    if not isinstance(widget_payload, dict):
        if not payload.get("ready"):
            return
        return
    sanitized_widget = sanitize_for_json(widget_payload)
    ctx.stock_widget_seeded = True
    ctx.reused_stock = ctx.reused_stock or bool(payload.get("from_cache"))
    _set_market_artifact(
        ctx,
        widget=sanitized_widget,
        error=payload.get("error"),
        error_code=payload.get("error_code"),
    )


def _set_analysis_artifact(
    ctx: PlannerPhaseContext,
    *,
    analysis_text: str,
    fragments: List[str],
    tool_bundle: Optional[Dict[str, Any]],
    summary: Optional[str],
    bullets: Optional[List[str]],
    key_numbers: Optional[List[str]],
    risk_watch: Optional[List[str]],
    next_steps: Optional[List[str]],
) -> None:
    stock_widget = None
    if tool_bundle:
        stock_widget = tool_bundle.get("stock_widget")
    web_context = None
    if ctx.artifacts.web:
        web_context = ctx.artifacts.web.to_dict()
    elif ctx.web_search is not None:
        web_context = ctx.web_search.to_payload()
    elif ctx.snapshot_artifacts and ctx.snapshot_artifacts.web:
        web_context = ctx.snapshot_artifacts.web.to_dict()
    evidence_entries = _build_evidence_entries(
        web_context=web_context,
        highlights=bullets,
        summary=summary,
    )
    ctx.artifacts.analysis = AnalysisArtifact(
        query=ctx.query,
        analysis_text=analysis_text or None,
        fragments=fragments,
        length=len(analysis_text),
        summary=summary,
        highlights=bullets or [],
        key_numbers=key_numbers or [],
        risk_watch=risk_watch or [],
        next_steps=next_steps or [],
        evidence=evidence_entries,
        stock_widget=stock_widget,
        web_context=web_context,
        tool_bundle=tool_bundle or None,
    )


def _build_planner_result_payload(ctx: PlannerPhaseContext) -> Dict[str, Any]:
    intent_model = ctx.intent
    if intent_model is not None and not isinstance(intent_model, IntentModel):
        intent_payload: Optional[Dict[str, Any]] = None
        if hasattr(intent_model, "model_dump"):
            intent_payload = intent_model.model_dump()
        elif hasattr(intent_model, "__dict__"):
            intent_payload = dict(intent_model.__dict__)
        if isinstance(intent_payload, dict):
            try:
                intent_model = IntentModel(**intent_payload)
            except Exception:
                intent_model = None

    clarification_requests_raw = list(ctx.clarifications)
    clarification_requests: List[ClarifyRequestModel] = []
    for request in clarification_requests_raw:
        if isinstance(request, ClarifyRequestModel):
            clarification_requests.append(request)
            continue
        request_payload: Optional[Dict[str, Any]] = None
        if hasattr(request, "model_dump"):
            request_payload = request.model_dump()
        elif isinstance(request, dict):
            request_payload = request
        elif hasattr(request, "__dict__"):
            request_payload = dict(request.__dict__)
        if isinstance(request_payload, dict):
            try:
                clarification_requests.append(ClarifyRequestModel(**request_payload))
            except Exception:
                continue

    sql_attempts: List[Dict[str, Any]] = []
    sql_text: Optional[str] = None
    if ctx.artifacts.sql_generation:
        sql_attempts = list(ctx.artifacts.sql_generation.attempts or [])
        sql_text = ctx.artifacts.sql_generation.sql

    row_count: Optional[int] = None
    if ctx.artifacts.sql_execution:
        row_count = ctx.artifacts.sql_execution.row_count

    chart_summary: Optional[Dict[str, Any]] = None
    if ctx.artifacts.chart:
        chart_summary = {
            "chart_type": ctx.artifacts.chart.chart_type,
            "series_count": ctx.artifacts.chart.series_count,
            "design": copy.deepcopy(ctx.artifacts.chart.design),
        }
        if ctx.artifacts.chart.scope_banner:
            chart_summary["scope_banner"] = ctx.artifacts.chart.scope_banner

    analysis_text = ctx.artifacts.analysis.analysis_text if ctx.artifacts.analysis else None

    metadata: Dict[str, Any] = {}
    if ctx.classification is not None:
        metadata["classification"] = copy.deepcopy(ctx.classification.model_dump())
    if ctx.clarification_sources:
        metadata["clarification_sources"] = sorted(ctx.clarification_sources)

    web_payload: Optional[Dict[str, Any]] = None
    if ctx.artifacts.web:
        web_payload = ctx.artifacts.web.to_dict()
    elif ctx.web_search is not None:
        web_payload = ctx.web_search.to_payload()
    elif ctx.snapshot_artifacts and ctx.snapshot_artifacts.web:
        web_payload = ctx.snapshot_artifacts.web.to_dict()
    web_latency: Optional[Dict[str, Any]] = None
    if web_payload:
        metadata["web_search"] = copy.deepcopy(web_payload)
        stats = web_payload.get("latency_stats")
        if isinstance(stats, dict):
            web_latency = {
                "total_ms": stats.get("total_ms") or stats.get("totalMs"),
                "p50_ms": stats.get("p50_ms") or stats.get("p50Ms"),
                "max_ms": stats.get("max_ms") or stats.get("maxMs"),
                "min_ms": stats.get("min_ms") or stats.get("minMs"),
                "samples": stats.get("samples") or stats.get("latency_samples") or stats.get("sample_count"),
            }
    elif ctx.web_search is not None and ctx.web_search.latency_ms is not None:
        web_latency = {
            "total_ms": ctx.web_search.latency_ms,
        }

    if web_latency:
        cleaned_latency = {key: value for key, value in web_latency.items() if value is not None}
        if cleaned_latency:
            metadata["web_search_latency"] = cleaned_latency
        guardrail_payload = _evaluate_latency_guardrail(web_latency)
        if guardrail_payload:
            metadata["web_search_guardrail"] = guardrail_payload

    if ctx.artifacts.analysis:
        overview: Dict[str, Any] = {}
        if ctx.artifacts.analysis.summary:
            overview["tldr"] = ctx.artifacts.analysis.summary
        if ctx.artifacts.analysis.highlights:
            overview["highlights"] = list(ctx.artifacts.analysis.highlights)
        if ctx.artifacts.analysis.key_numbers:
            overview["key_numbers"] = list(ctx.artifacts.analysis.key_numbers)
        if ctx.artifacts.analysis.risk_watch:
            overview["risk_watch"] = list(ctx.artifacts.analysis.risk_watch)
        if ctx.artifacts.analysis.next_steps:
            overview["next_steps"] = list(ctx.artifacts.analysis.next_steps)
        evidence_entries = list(ctx.artifacts.analysis.evidence or [])
        if not evidence_entries:
            web_source: Optional[Dict[str, Any]] = None
            if metadata.get("web_search"):
                web_candidate = metadata.get("web_search")
                if isinstance(web_candidate, dict):
                    web_source = web_candidate
            elif ctx.artifacts.web:
                web_source = ctx.artifacts.web.to_dict()
            evidence_entries = _build_evidence_entries(
                web_context=web_source,
                highlights=ctx.artifacts.analysis.highlights,
                summary=ctx.artifacts.analysis.summary or ctx.artifacts.analysis.analysis_text,
            )
            if evidence_entries:
                ctx.artifacts.analysis.evidence = evidence_entries
        if evidence_entries:
            overview["evidence"] = evidence_entries
        if overview:
            metadata["analysis_overview"] = overview

    if SCHEMA_CLARIFIER_ENABLED:
        decision = ctx.schema_clarifier_decision
        metadata["schema_clarifier"] = {
            "enabled": True,
            "action": decision.action if decision else "disabled",
            "missing_slots": list(decision.missing_slots) if decision and decision.missing_slots else [],
            "slot": decision.slot if decision else None,
        }

    metadata["follow_up_route"] = ctx.follow_up_route.value
    metadata["snapshot_reuse"] = {
        "reused_sql": ctx.reused_sql,
        "reused_chart": ctx.reused_chart,
        "reused_stock": ctx.reused_stock,
        "reused_web": ctx.reused_web,
        "reused_analysis": ctx.reused_analysis,
        "criteria_changed": ctx.criteria_changed,
        "follow_up_route": ctx.follow_up_route.value,
        "source": "snapshot" if ctx.reuse_snapshot_active else None,
        "snapshot_age_seconds": ctx.snapshot_age_seconds,
        "snapshot_stale": ctx.snapshot_stale,
    }
    metadata["reuse_snapshot"] = metadata["snapshot_reuse"]

    planner_result_model = PlannerResultModel(
        intent=intent_model,
        clarification_requests=clarification_requests,
        sql_attempts=sql_attempts,
        sql_text=sql_text,
        data_row_count=row_count,
        chart_summary=chart_summary,
        analysis=analysis_text,
        metadata=metadata,
    )
    return planner_result_model.model_dump()


def _artifacts_from_snapshot(snapshot: Optional[SessionStateSnapshot]) -> Optional[PipelineArtifacts]:
    if snapshot is None:
        return None
    analytics_cache = snapshot.tool_cache.get("analytics", {}) if hasattr(snapshot, "tool_cache") else {}
    artifacts_payload = analytics_cache.get("artifacts")
    if isinstance(artifacts_payload, dict):
        try:
            return PipelineArtifacts.from_dict(artifacts_payload)
        except Exception:
            return None
    return None


def _dataset_preview_from_snapshot(snapshot: Optional[SessionStateSnapshot]) -> Optional[Dict[str, Any]]:
    if snapshot is None or not hasattr(snapshot, "tool_cache"):
        return None
    preview_payload = snapshot.tool_cache.get("planner_dataset_preview")
    if isinstance(preview_payload, dict):
        rows = preview_payload.get("rows")
        if isinstance(rows, list):
            return preview_payload
    return None


def _snapshot_age_seconds_from_snapshot(snapshot: Dict[str, Any]) -> Optional[float]:
    updated_at = snapshot.get("updated_at")
    if not isinstance(updated_at, str):
        return None
    try:
        stamp = datetime.fromisoformat(updated_at)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        delta = datetime.utcnow() - stamp
    else:
        delta = datetime.now(stamp.tzinfo) - stamp
    return max(delta.total_seconds(), 0.0)


def _is_snapshot_fresh(snapshot: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(snapshot, dict):
        return False
    age_seconds = _snapshot_age_seconds_from_snapshot(snapshot)
    if age_seconds is None:
        return False
    return age_seconds <= SNAPSHOT_MAX_AGE_SECONDS

def _clear_tool_state(
    ctx: PlannerPhaseContext,
    tool_names: Iterable[str],
) -> None:
    names = {str(name).strip().lower() for name in tool_names if name}
    if not names:
        return
    receipts = getattr(ctx, "tool_receipts", None)
    if isinstance(receipts, dict):
        for key in list(receipts.keys()):
            if str(key).strip().lower() in names:
                receipts.pop(key, None)
    results = getattr(ctx, "tool_parallel_results", None)
    if isinstance(results, list):
        filtered = []
        for entry in results:
            tool_id = str((entry or {}).get("tool") or "").strip().lower()
            event_id = str((entry or {}).get("event") or "").strip().lower()
            lane_id = str((entry or {}).get("lane") or "").strip().lower()
            if tool_id in names or event_id in names or lane_id in {"web", "market"} and tool_id in names:
                continue
            filtered.append(entry)
        ctx.tool_parallel_results = filtered
    manifest = getattr(ctx, "tool_parallel_manifest", None)
    if isinstance(manifest, list):
        ctx.tool_parallel_manifest = [
            entry for entry in manifest if str((entry or {}).get("tool") or "").strip().lower() not in names
        ]

def _reset_revision_accessories(ctx: PlannerPhaseContext, lanes: Iterable[str]) -> None:
    lanes_normalized = {str(lane).strip().lower() for lane in lanes if lane}
    if not lanes_normalized:
        return
    if "web" in lanes_normalized:
        ctx.web_search = None
        ctx.web_search_seeded = False
        ctx.reused_web = False
        ctx.web_ready_emitted = False  # type: ignore[attr-defined]
        _clear_tool_state(ctx, _WEB_TOOL_NAMES)
    if "market" in lanes_normalized or "stock" in lanes_normalized:
        ctx.stock_widget_seeded = False
        ctx.reused_stock = False
        ctx.stock_ready_emitted = False  # type: ignore[attr-defined]
        _clear_tool_state(ctx, _MARKET_TOOL_NAMES)
    ctx.accessories_prefetched = False


def _build_revision_snapshot_payload(ctx: PlannerPhaseContext) -> Optional[Dict[str, Any]]:
    plan_model: Optional[QueryPlanModel] = getattr(ctx, "plan", None) or getattr(ctx, "provisional_plan", None)
    if plan_model is None:
        plan_model = QueryPlanModel()
        ctx.plan = plan_model
        ctx.provisional_plan = plan_model

    signature = ctx.intent_signature or build_intent_signature(ctx.intent, plan_model)
    if signature is None:
        signature = {
            "query": (ctx.query or "")[:256],
            "generated_at": datetime.utcnow().isoformat(),
            "reason": "missing_intent_signature",
        }

    payload: Dict[str, Any] = {"intent_signature": signature}

    classification_model = getattr(ctx, "classification", None)
    if classification_model is not None:
        try:
            payload["classification"] = classification_model.model_dump()
        except Exception:
            payload["classification"] = sanitize_for_json(classification_model)

    sql_generation = ctx.artifacts.sql_generation
    if sql_generation and sql_generation.sql:
        payload["sql"] = sql_generation.sql

    sql_execution = ctx.artifacts.sql_execution
    if sql_execution:
        if sql_execution.row_count is not None:
            payload["sql_row_count"] = sql_execution.row_count
        if sql_execution.columns:
            payload["columns"] = list(sql_execution.columns)
        sample_source = sql_execution.sample_rows or sql_execution.dataset_preview
        samples = limit_sample_rows(sample_source)
        if samples:
            payload["data_sample"] = samples

    chart_artifact = ctx.artifacts.chart
    if chart_artifact:
        if chart_artifact.spec:
            payload["chart_spec"] = copy.deepcopy(chart_artifact.spec)
        if chart_artifact.spec_id:
            payload["chart_spec_id"] = chart_artifact.spec_id

    analysis_artifact = ctx.artifacts.analysis
    if analysis_artifact:
        if analysis_artifact.analysis_text:
            payload["analysis"] = analysis_artifact.analysis_text
            if analysis_artifact.length is not None:
                payload["analysis_length"] = analysis_artifact.length
        if analysis_artifact.stock_widget and analysis_artifact.stock_widget not in ({}, None):
            payload["stock_widget"] = copy.deepcopy(analysis_artifact.stock_widget)
        if analysis_artifact.web_context and analysis_artifact.web_context not in ({}, None):
            payload["web_context"] = copy.deepcopy(analysis_artifact.web_context)

    if ctx.web_search is not None and not payload.get("web_context"):
        try:
            payload["web_context"] = ctx.web_search.to_payload()
        except Exception:
            pass

    if ctx.artifacts.market and ctx.artifacts.market.snapshot and not payload.get("stock_widget"):
        payload["stock_widget"] = copy.deepcopy(ctx.artifacts.market.snapshot)

    intent_model = getattr(ctx, "intent", None)
    if intent_model is not None:
        try:
            payload["intent"] = intent_model.model_dump()
        except Exception:
            payload["intent"] = sanitize_for_json(intent_model)

    if plan_model is not None:
        try:
            payload["plan"] = plan_model.model_dump()
        except Exception:
            plan_payload = getattr(plan_model, "dict", None)
            payload["plan"] = plan_payload() if callable(plan_payload) else sanitize_for_json(plan_model)

    intent_resolution = getattr(ctx, "intent_resolution", None)
    if intent_resolution is not None:
        try:
            payload["intent_resolution"] = intent_resolution.model_dump()
        except Exception:
            payload["intent_resolution"] = sanitize_for_json(intent_resolution)

    slot_statuses_payload: Dict[str, Any] = {}
    for slot_name, status in (getattr(ctx, "slot_statuses", {}) or {}).items():
        if isinstance(status, SlotStatusModel):
            try:
                slot_statuses_payload[str(slot_name)] = status.model_dump()
            except Exception:
                slot_statuses_payload[str(slot_name)] = sanitize_for_json(status)
        elif isinstance(status, Mapping):
            slot_statuses_payload[str(slot_name)] = dict(status)
    if slot_statuses_payload:
        payload["slot_statuses"] = slot_statuses_payload

    followup_payload: List[Dict[str, Any]] = []
    for followup in getattr(ctx, "slot_followups", []) or []:
        if isinstance(followup, FollowUpModel):
            try:
                followup_payload.append(followup.model_dump())
            except Exception:
                followup_payload.append(sanitize_for_json(followup))
        elif isinstance(followup, Mapping):
            followup_payload.append(dict(followup))
    if followup_payload:
        payload["slot_followups"] = followup_payload

    clarification_payload: List[Dict[str, Any]] = []
    for clarification in getattr(ctx, "clarifications", []) or []:
        if isinstance(clarification, ClarifyRequestModel):
            try:
                clarification_payload.append(clarification.model_dump())
            except Exception:
                clarification_payload.append(sanitize_for_json(clarification))
        elif isinstance(clarification, Mapping):
            clarification_payload.append(dict(clarification))
    if clarification_payload:
        payload["clarifications"] = clarification_payload

    clarification_rounds = getattr(ctx, "clarification_rounds", 0)
    if isinstance(clarification_rounds, int) and clarification_rounds > 0:
        payload["clarification_rounds"] = clarification_rounds

    assumptions = getattr(ctx, "assumptions", None)
    if isinstance(assumptions, (list, tuple, set)) and assumptions:
        payload["assumptions"] = [str(item) for item in assumptions if item not in (None, "")]

    payload["updated_at"] = datetime.utcnow().isoformat()
    sanitized = sanitize_for_json(payload)
    return sanitized if isinstance(sanitized, dict) else None


def _compose_reused_analysis_payload(ctx: PlannerPhaseContext) -> Optional[Dict[str, Any]]:
    artifact = ctx.artifacts.analysis
    if artifact is None and ctx.snapshot_artifacts and ctx.snapshot_artifacts.analysis:
        artifact = ctx.snapshot_artifacts.analysis
    if artifact is None:
        return None

    artifact_dict = artifact.to_dict()
    if not artifact_dict:
        return None

    payload: Dict[str, Any] = {}
    analysis_text = artifact_dict.get("analysis_text")
    if analysis_text:
        payload["analysis"] = analysis_text
        payload["analysis_length"] = artifact_dict.get("length") or len(analysis_text)
    summary = artifact_dict.get("summary")
    if summary:
        payload["tldr"] = summary
    highlights = artifact_dict.get("highlights")
    if highlights:
        payload["bullets"] = highlights
    key_numbers = artifact_dict.get("key_numbers")
    if key_numbers:
        payload["key_numbers"] = key_numbers
    risk_watch = artifact_dict.get("risk_watch")
    if risk_watch:
        payload["risk_watch"] = risk_watch
    next_steps = artifact_dict.get("next_steps")
    if next_steps:
        payload["next_steps"] = next_steps
    stock_widget = artifact_dict.get("stock_widget")
    if stock_widget:
        payload["stock_widget"] = stock_widget
    web_context = artifact_dict.get("web_context")
    if web_context:
        payload["web_context"] = web_context
    evidence = artifact_dict.get("evidence")
    if evidence:
        payload["evidence"] = evidence
    tool_bundle = artifact_dict.get("tool_bundle")
    if tool_bundle:
        payload["tool_bundle"] = tool_bundle

    payload["refresh_mode"] = getattr(ctx, "analysis_refresh_mode", "full")

    sanitized = sanitize_for_json(payload)
    return sanitized or None


def _build_reused_analysis_event(flow_mode: FlowMode, ctx: PlannerPhaseContext) -> Optional[Dict[str, Any]]:
    payload = _compose_reused_analysis_payload(ctx)
    if not payload:
        return None
    event = EventEmitter.result("analysis_complete", payload, key="analysis")
    event["event"] = "analysis_complete"
    event["data"]["ts"] = datetime.utcnow().isoformat()
    event["data"]["reused"] = True
    event["data"]["flow_mode"] = flow_mode.value
    event["data"]["lane"] = "analysis"
    event["data"]["refresh_mode"] = getattr(ctx, "analysis_refresh_mode", "full")
    return event


def _compose_reused_analysis_payload(ctx: PlannerPhaseContext) -> Optional[Dict[str, Any]]:
    artifact = ctx.artifacts.analysis
    if artifact is None and ctx.snapshot_artifacts and ctx.snapshot_artifacts.analysis:
        artifact = ctx.snapshot_artifacts.analysis
    if artifact is None:
        return None

    artifact_dict = artifact.to_dict()
    if not artifact_dict:
        return None

    payload: Dict[str, Any] = {}
    analysis_text = artifact_dict.get("analysis_text")
    if analysis_text:
        payload["analysis"] = analysis_text
        payload["analysis_length"] = artifact_dict.get("length") or len(analysis_text)
    summary = artifact_dict.get("summary")
    if summary:
        payload["tldr"] = summary
    highlights = artifact_dict.get("highlights")
    if highlights:
        payload["bullets"] = highlights
    key_numbers = artifact_dict.get("key_numbers")
    if key_numbers:
        payload["key_numbers"] = key_numbers
    risk_watch = artifact_dict.get("risk_watch")
    if risk_watch:
        payload["risk_watch"] = risk_watch
    next_steps = artifact_dict.get("next_steps")
    if next_steps:
        payload["next_steps"] = next_steps
    stock_widget = artifact_dict.get("stock_widget")
    if stock_widget:
        payload["stock_widget"] = stock_widget
    web_context = artifact_dict.get("web_context")
    if web_context:
        payload["web_context"] = web_context
    evidence = artifact_dict.get("evidence")
    if evidence:
        payload["evidence"] = evidence
    tool_bundle = artifact_dict.get("tool_bundle")
    if tool_bundle:
        payload["tool_bundle"] = tool_bundle

    payload["refresh_mode"] = getattr(ctx, "analysis_refresh_mode", "full")

    sanitized = sanitize_for_json(payload)
    return sanitized or None


def _build_reused_analysis_event(flow_mode: FlowMode, ctx: PlannerPhaseContext) -> Optional[Dict[str, Any]]:
    payload = _compose_reused_analysis_payload(ctx)
    if not payload:
        return None
    event = EventEmitter.result("analysis_complete", payload, key="analysis")
    event["event"] = "analysis_complete"
    event["data"]["ts"] = datetime.utcnow().isoformat()
    event["data"]["reused"] = True
    event["data"]["flow_mode"] = flow_mode.value
    event["data"]["lane"] = "analysis"
    event["data"]["refresh_mode"] = getattr(ctx, "analysis_refresh_mode", "full")
    return event


def compose_web_ready_payload(ctx: PlannerPhaseContext) -> Optional[Dict[str, Any]]:
    web_payload: Optional[Dict[str, Any]] = None
    if ctx.artifacts.analysis and ctx.artifacts.analysis.web_context:
        web_payload = copy.deepcopy(ctx.artifacts.analysis.web_context)
    elif ctx.revision_snapshot and ctx.revision_snapshot.get("web_context"):
        web_payload = copy.deepcopy(ctx.revision_snapshot["web_context"])
    elif ctx.artifacts.web and ctx.artifacts.web.to_dict():
        web_payload = ctx.artifacts.web.to_dict()
    if not web_payload:
        return None
    payload = sanitize_for_json(web_payload) or {}
    if not isinstance(payload, dict):
        return None
    payload["reused"] = bool(getattr(ctx, "reused_web", False))
    payload["from_cache"] = bool(payload.get("reused"))
    if "source" not in payload and getattr(ctx, "is_revision_follow_up", False):
        payload["source"] = "fresh_revision"
    payload.setdefault("schedule_stage", "hedged_accessories")
    if ctx.snapshot_age_seconds is not None:
        payload["snapshot_age_seconds"] = ctx.snapshot_age_seconds
    return payload


def _build_analysis_source_summaries(
    *,
    artifacts: Optional[PipelineArtifacts],
    tool_sources: Optional[Mapping[str, Any]] = None,
    stock_widget: Optional[Mapping[str, Any]] = None,
    web_context: Optional[Mapping[str, Any]] = None,
    reused_flags: Optional[Mapping[str, bool]] = None,
) -> Dict[str, Any]:
    if artifacts is None:
        artifacts = PipelineArtifacts()

    lane_status: Dict[str, str] = {}
    if isinstance(tool_sources, Mapping):
        for raw_name, status in tool_sources.items():
            if not isinstance(raw_name, str):
                continue
            tool_name = raw_name.strip().lower()
            lane = _TOOL_TO_ANALYSIS_LANE.get(tool_name)
            if not lane:
                continue
            normalized = str(status).strip().lower()
            if not normalized:
                continue
            lane_status.setdefault(lane, normalized)

    reused_lookup = {key: bool(value) for key, value in (reused_flags or {}).items()}

    def lane_reused(lane: str) -> bool:
        if lane in reused_lookup:
            return reused_lookup[lane]
        return lane_status.get(lane) == "cached"

    def compact(entry: Dict[str, Any]) -> Dict[str, Any]:
        cleaned: Dict[str, Any] = {}
        for key, value in entry.items():
            if value is None:
                continue
            if isinstance(value, (list, dict)) and not value:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            cleaned[key] = value
        return cleaned

    sources: Dict[str, Dict[str, Any]] = {}

    sql_execution = getattr(artifacts, "sql_execution", None)
    if sql_execution:
        columns = list(sql_execution.columns[:6]) if isinstance(sql_execution.columns, list) else []
        metrics = list(sql_execution.metrics[:3]) if isinstance(sql_execution.metrics, list) else []
        timeframe = sql_execution.timeframe if isinstance(sql_execution.timeframe, Mapping) else None
        summary_parts: List[str] = []
        if isinstance(sql_execution.row_count, int):
            summary_parts.append(f"{sql_execution.row_count:,} rows")
        if columns:
            summary_parts.append(f"columns: {', '.join(columns[:4])}")
        if timeframe and timeframe.get("start") and timeframe.get("end"):
            summary_parts.append(f"timeframe: {timeframe['start']} to {timeframe['end']}")
        entry = compact(
            {
                "lane": "sql",
                "label": "SQL data",
                "summary": " | ".join(summary_parts) if summary_parts else None,
                "row_count": sql_execution.row_count,
                "columns": columns,
                "metrics": metrics,
                "reused": lane_reused("sql"),
            }
        )
        if entry:
            sources["sql"] = entry

    widget_candidate: Optional[Mapping[str, Any]] = None
    if isinstance(stock_widget, Mapping):
        widget_candidate = stock_widget
    elif artifacts.analysis and isinstance(artifacts.analysis.stock_widget, Mapping):
        widget_candidate = artifacts.analysis.stock_widget
    elif artifacts.market and isinstance(artifacts.market.snapshot, Mapping):
        widget_candidate = artifacts.market.snapshot

    if widget_candidate:
        symbols: List[str] = []
        raw_symbols = widget_candidate.get("symbols")
        if isinstance(raw_symbols, list):
            for entry in raw_symbols:
                if isinstance(entry, (list, tuple)) and entry:
                    candidate = entry[1] if len(entry) > 1 else entry[0]
                else:
                    candidate = entry
                if isinstance(candidate, str) and candidate.strip():
                    symbols.append(candidate.strip().upper())
        summary_parts: List[str] = []
        if symbols:
            summary_parts.append(f"symbols: {', '.join(symbols[:3])}")
        insights = widget_candidate.get("insights") if isinstance(widget_candidate.get("insights"), Mapping) else None
        latest_close = None
        change_percent = None
        if insights:
            latest_close = insights.get("latest_close")
            change_percent = insights.get("change_percent")
        else:
            latest_close = widget_candidate.get("latest_close")
            change_percent = widget_candidate.get("change_percent")
        if isinstance(latest_close, (int, float)):
            summary_parts.append(f"latest close: {latest_close}")
        if isinstance(change_percent, (int, float)):
            summary_parts.append(f"change: {change_percent:+.2f}%")
        entry = compact(
            {
                "lane": "stock",
                "label": "Stock data",
                "summary": " | ".join(summary_parts) if summary_parts else None,
                "symbols": symbols[:4],
                "latest_close": latest_close if isinstance(latest_close, (int, float)) else None,
                "change_percent": change_percent if isinstance(change_percent, (int, float)) else None,
                "reused": lane_reused("stock"),
            }
        )
        if entry:
            sources["stock"] = entry

    context_candidate: Optional[Mapping[str, Any]] = None
    if isinstance(web_context, Mapping):
        context_candidate = web_context
    elif artifacts.analysis and isinstance(artifacts.analysis.web_context, Mapping):
        context_candidate = artifacts.analysis.web_context
    elif artifacts.web and isinstance(artifacts.web.to_dict(), dict):
        context_candidate = artifacts.web.to_dict()

    if context_candidate:
        summary_text = context_candidate.get("summary")
        topic = (
            context_candidate.get("search_topic")
            or context_candidate.get("searchTopic")
            or context_candidate.get("query")
        )
        snippets = context_candidate.get("snippets") or context_candidate.get("articles")
        snippet_count = len(snippets) if isinstance(snippets, list) else 0
        entry = compact(
            {
                "lane": "web",
                "label": "Online research",
                "summary": summary_text if isinstance(summary_text, str) else None,
                "topic": topic if isinstance(topic, str) else None,
                "snippet_count": snippet_count,
                "reused": lane_reused("web"),
            }
        )
        if entry:
            sources["web"] = entry

    if not sources:
        return {}
    sanitized = sanitize_for_json(sources)
    return sanitized if isinstance(sanitized, dict) else {}

def _hydrate_context_from_snapshot(
    ctx: PlannerPhaseContext,
    snapshot: Optional[SessionStateSnapshot],
    artifacts: Optional[PipelineArtifacts],
) -> None:
    revision_snapshot = extract_revision_snapshot(snapshot)
    if revision_snapshot:
        ctx.revision_snapshot = copy.deepcopy(revision_snapshot)
        ctx.prior_intent_signature = revision_snapshot.get("intent_signature")
    else:
        ctx.revision_snapshot = None
        ctx.prior_intent_signature = None

    if ctx.revision_snapshot:
        def _coerce_model(model_cls, payload):
            if not isinstance(payload, Mapping):
                return None
            try:
                if hasattr(model_cls, "model_validate"):
                    return model_cls.model_validate(payload)
                if hasattr(model_cls, "parse_obj"):
                    return model_cls.parse_obj(payload)  # type: ignore[attr-defined]
                return model_cls(**payload)
            except Exception:
                return None

        hydrated_intent: Optional[IntentModel] = None
        intent_payload = ctx.revision_snapshot.get("intent")
        if intent_payload and getattr(ctx, "intent", None) is None:
            intent_model = _coerce_model(IntentModel, intent_payload)
            if intent_model:
                hydrated_intent = intent_model
                ctx.intent = intent_model

        plan_payload = ctx.revision_snapshot.get("plan")
        if plan_payload:
            plan_model = _coerce_model(QueryPlanModel, plan_payload)
            if plan_model:
                ctx.plan = plan_model
                ctx.provisional_plan = plan_model

        resolution_payload = ctx.revision_snapshot.get("intent_resolution")
        slot_status_models: Dict[str, SlotStatusModel] = {}
        followup_models: List[FollowUpModel] = []
        if resolution_payload:
            resolution_model = _coerce_model(IntentResolutionModel, resolution_payload)
            if resolution_model:
                ctx.intent_resolution = resolution_model
                slot_status_models = dict(resolution_model.slots or {})
                followup_models = list(resolution_model.followups or [])

        slot_status_payload = ctx.revision_snapshot.get("slot_statuses")
        if isinstance(slot_status_payload, Mapping):
            for slot_name, raw in slot_status_payload.items():
                if slot_name in slot_status_models:
                    continue
                status_model = _coerce_model(SlotStatusModel, raw)
                if status_model:
                    slot_status_models[str(slot_name)] = status_model
        if slot_status_models:
            ctx.slot_statuses = slot_status_models

        followup_payload = ctx.revision_snapshot.get("slot_followups")
        if isinstance(followup_payload, Sequence):
            for raw in followup_payload:
                followup_model = _coerce_model(FollowUpModel, raw)
                if followup_model:
                    followup_models.append(followup_model)
        if followup_models:
            ctx.slot_followups = followup_models

        if getattr(ctx, "intent_resolution", None) is None and (slot_status_models or followup_models):
            ctx.intent_resolution = IntentResolutionModel(
                slots=slot_status_models or {},
                followups=followup_models or [],
            )
        elif getattr(ctx, "intent_resolution", None) is not None:
            ctx.intent_resolution = ctx.intent_resolution.model_copy(  # type: ignore[assignment]
                update={
                    "slots": slot_status_models or dict(ctx.intent_resolution.slots or {}),
                    "followups": followup_models or list(ctx.intent_resolution.followups or []),
                }
            )

        clarifications_payload = ctx.revision_snapshot.get("clarifications")
        if isinstance(clarifications_payload, Sequence):
            clarifications: List[ClarifyRequestModel] = []
            for raw in clarifications_payload:
                clarification_model = _coerce_model(ClarifyRequestModel, raw)
                if clarification_model:
                    clarifications.append(clarification_model)
            if clarifications:
                ctx.clarifications = clarifications

        rounds_value = ctx.revision_snapshot.get("clarification_rounds")
        if isinstance(rounds_value, int) and rounds_value > 0:
            ctx.clarification_rounds = max(ctx.clarification_rounds, rounds_value)

        assumptions_payload = ctx.revision_snapshot.get("assumptions")
        if isinstance(assumptions_payload, Sequence) and assumptions_payload:
            ctx.assumptions = [str(item) for item in assumptions_payload if item not in (None, "")]
        elif hydrated_intent and getattr(hydrated_intent, "assumptions", None):
            ctx.assumptions = list(hydrated_intent.assumptions or [])
        elif getattr(ctx, "intent", None) and getattr(ctx.intent, "assumptions", None):
            ctx.assumptions = list(ctx.intent.assumptions or [])

        if ctx.prior_intent_signature and not getattr(ctx, "intent_signature", None):
            ctx.intent_signature = copy.deepcopy(ctx.prior_intent_signature)

        ctx.reuse_snapshot_active = True

    if artifacts is None:
        if ctx.revision_snapshot:
            artifacts = PipelineArtifacts()
        else:
            return

    if ctx.revision_snapshot:
        chart_spec = ctx.revision_snapshot.get("chart_spec")
        if chart_spec and artifacts.chart is None:
            artifacts.chart = ChartArtifact(
                query=ctx.query,
                spec=copy.deepcopy(chart_spec),
                spec_id=ctx.revision_snapshot.get("chart_spec_id"),
            )
        if ctx.revision_snapshot.get("sql") and artifacts.sql_generation is None:
            artifacts.sql_generation = SQLGenerationArtifact(
                query=ctx.query,
                sql=ctx.revision_snapshot.get("sql"),
                status="completed",
            )
        if artifacts.sql_execution is None:
            if ctx.revision_snapshot.get("sql_row_count") is not None or ctx.revision_snapshot.get("data_sample"):
                artifacts.sql_execution = SQLExecutionArtifact(
                    query=ctx.query,
                    row_count=ctx.revision_snapshot.get("sql_row_count"),
                    columns=list(ctx.revision_snapshot.get("columns") or []),
                    sample_rows=limit_sample_rows(ctx.revision_snapshot.get("data_sample") or []),
                    dataset_preview=limit_sample_rows(ctx.revision_snapshot.get("data_sample") or []),
                    status="completed",
                )
        if artifacts.analysis is None and (
            ctx.revision_snapshot.get("analysis")
            or ctx.revision_snapshot.get("stock_widget")
            or ctx.revision_snapshot.get("web_context")
        ):
            artifacts.analysis = AnalysisArtifact(
                query=ctx.query,
                analysis_text=ctx.revision_snapshot.get("analysis"),
                length=ctx.revision_snapshot.get("analysis_length"),
                stock_widget=copy.deepcopy(ctx.revision_snapshot.get("stock_widget")) if ctx.revision_snapshot.get("stock_widget") else None,
                web_context=copy.deepcopy(ctx.revision_snapshot.get("web_context")) if ctx.revision_snapshot.get("web_context") else None,
            )
        if artifacts.web is None and isinstance(ctx.revision_snapshot.get("web_context"), dict):
            web_payload = copy.deepcopy(ctx.revision_snapshot["web_context"])
            artifacts.web = WebContextArtifact(
                query=ctx.query,
                summary=web_payload.get("summary"),
                snippets=list(web_payload.get("snippets") or []),
                search_id=web_payload.get("search_id"),
                from_cache=web_payload.get("from_cache"),
                metadata=copy.deepcopy(web_payload.get("metadata") or {}),
                topic=web_payload.get("topic"),
                latency_stats=web_payload.get("latency_stats"),
            )

    cached_tool_results: List[Dict[str, Any]] = []
    if ctx.revision_snapshot:
        stock_snapshot = ctx.revision_snapshot.get("stock_widget")
        if stock_snapshot:
            cached_tool_results.append(
                {
                    "tool": "stock_tracker",
                    "status": "completed",
                    "payload": {"stock_widget": copy.deepcopy(stock_snapshot)},
                    "reused": True,
                }
            )
        web_snapshot = ctx.revision_snapshot.get("web_context")
        if isinstance(web_snapshot, dict) and web_snapshot:
            cached_tool_results.append(
                {
                    "tool": "web_retriever",
                    "status": "completed",
                    "payload": copy.deepcopy(web_snapshot),
                    "reused": True,
                }
            )
    if cached_tool_results:
        ctx.tool_parallel_results = cached_tool_results
    if ctx.revision_snapshot and ctx.revision_snapshot.get("web_context") and getattr(ctx, "web_search", None) is None:
        web_ctx_payload = copy.deepcopy(ctx.revision_snapshot["web_context"])
        ctx.web_search = SimpleNamespace(
            to_payload=lambda payload=web_ctx_payload: copy.deepcopy(payload),
            summary=web_ctx_payload.get("summary"),
            latency_ms=web_ctx_payload.get("latency_ms"),
        )
    if ctx.revision_snapshot and ctx.revision_snapshot.get("stock_widget"):
        ctx.stock_widget_seeded = True
    if ctx.revision_snapshot and ctx.revision_snapshot.get("web_context"):
        ctx.web_search_seeded = True
    ctx.artifacts = artifacts
    ctx.snapshot_artifacts = artifacts
    execution_artifact = getattr(ctx.artifacts, "sql_execution", None)
    preview_payload = _dataset_preview_from_snapshot(snapshot)
    if execution_artifact and preview_payload:
        rows = list(preview_payload.get("rows") or [])
        if rows:
            execution_artifact.dataset_preview = rows
            if not getattr(execution_artifact, "dataset", None):
                execution_artifact.dataset = list(rows)
            if execution_artifact.row_count is None:
                row_count = preview_payload.get("row_count")
                normalized_row_count = normalize_row_count(row_count)
                if normalized_row_count is not None:
                    execution_artifact.row_count = normalized_row_count


def _apply_revision_context_hints(ctx: PlannerPhaseContext) -> None:
    revision_ctx = getattr(ctx, "revision_context", None)
    if revision_ctx is None:
        return
    refresh_flags = dict(getattr(ctx, "lane_refresh_required", {}) or {})
    candidate_lanes = ("analysis", "chart", "web", "market")
    for lane in candidate_lanes:
        needs_refresh = revision_ctx.should_refresh(lane)
        if needs_refresh is False:
            refresh_flags[lane] = False
        elif lane not in refresh_flags and needs_refresh is True:
            refresh_flags[lane] = True
    ctx.lane_refresh_required = refresh_flags
    if revision_ctx.reasoning_summaries and not ctx.revision_reasoning:
        ctx.revision_reasoning = copy.deepcopy(revision_ctx.reasoning_summaries)
    payload = getattr(revision_ctx, "snapshot_payload", None)
    if isinstance(payload, Mapping):
        if getattr(ctx, "revision_snapshot", None) is None:
            ctx.revision_snapshot = copy.deepcopy(payload)
        _hydrate_revision_payload(ctx, payload)


def _hydrate_revision_payload(ctx: PlannerPhaseContext, payload: Mapping[str, Any]) -> None:
    if not isinstance(payload, Mapping) or not payload:
        return

    def _coerce_model(model_cls, raw_payload):
        if not isinstance(raw_payload, Mapping):
            return None
        try:
            if hasattr(model_cls, "model_validate"):
                return model_cls.model_validate(raw_payload)  # type: ignore[attr-defined]
            if hasattr(model_cls, "parse_obj"):
                return model_cls.parse_obj(raw_payload)  # type: ignore[attr-defined]
            return model_cls(**raw_payload)
        except Exception:
            return None

    classification_payload = payload.get("classification")
    if classification_payload and getattr(ctx, "classification", None) is None:
        classification_model = _coerce_model(OffTopicClassifierSchema, classification_payload)
        if classification_model:
            ctx.classification = classification_model
            is_financial = getattr(classification_model, "is_financial_query", None)
            if is_financial is not None:
                ctx.is_financial_query = bool(is_financial)

    if getattr(ctx, "intent_signature", None) is None:
        signature = payload.get("intent_signature")
        if isinstance(signature, Mapping):
            ctx.intent_signature = copy.deepcopy(signature)

    hydrated_intent: Optional[IntentModel] = None
    if getattr(ctx, "intent", None) is None:
        intent_payload = payload.get("intent")
        if intent_payload:
            intent_model = _coerce_model(IntentModel, intent_payload)
            if intent_model:
                ctx.intent = intent_model
                hydrated_intent = intent_model
    plan_payload = payload.get("plan")
    if plan_payload and getattr(ctx, "plan", None) is None:
        plan_model = _coerce_model(QueryPlanModel, plan_payload)
        if plan_model:
            ctx.plan = plan_model
            ctx.provisional_plan = plan_model

    slot_status_models: Dict[str, SlotStatusModel] = {}
    followup_models: List[FollowUpModel] = []
    resolution_payload = payload.get("intent_resolution")
    if resolution_payload and getattr(ctx, "intent_resolution", None) is None:
        resolution_model = _coerce_model(IntentResolutionModel, resolution_payload)
        if resolution_model:
            ctx.intent_resolution = resolution_model
            slot_status_models = dict(resolution_model.slots or {})
            followup_models = list(resolution_model.followups or [])

    slot_status_payload = payload.get("slot_statuses")
    if isinstance(slot_status_payload, Mapping):
        for slot_name, raw in slot_status_payload.items():
            if slot_name in slot_status_models:
                continue
            status_model = _coerce_model(SlotStatusModel, raw)
            if status_model:
                slot_status_models[str(slot_name)] = status_model
    if slot_status_models:
        ctx.slot_statuses = slot_status_models

    followup_payload = payload.get("slot_followups")
    if isinstance(followup_payload, Sequence):
        for raw in followup_payload:
            followup_model = _coerce_model(FollowUpModel, raw)
            if followup_model:
                followup_models.append(followup_model)
    if followup_models:
        ctx.slot_followups = followup_models

    if getattr(ctx, "intent_resolution", None) is None and (slot_status_models or followup_models):
        ctx.intent_resolution = IntentResolutionModel(
            slots=slot_status_models or {},
            followups=followup_models or [],
        )
    elif getattr(ctx, "intent_resolution", None) is not None and slot_status_models:
        ctx.intent_resolution = ctx.intent_resolution.model_copy(  # type: ignore[assignment]
            update={
                "slots": slot_status_models or dict(ctx.intent_resolution.slots or {}),
                "followups": followup_models or list(ctx.intent_resolution.followups or []),
            }
        )

    clarifications_payload = payload.get("clarifications")
    if isinstance(clarifications_payload, Sequence) and not getattr(ctx, "clarifications", None):
        clarifications: List[ClarifyRequestModel] = []
        for raw in clarifications_payload:
            clarification_model = _coerce_model(ClarifyRequestModel, raw)
            if clarification_model:
                clarifications.append(clarification_model)
        if clarifications:
            ctx.clarifications = clarifications

    rounds_value = payload.get("clarification_rounds")
    if isinstance(rounds_value, int) and rounds_value > 0:
        ctx.clarification_rounds = max(ctx.clarification_rounds, rounds_value)

    assumptions_payload = payload.get("assumptions")
    if isinstance(assumptions_payload, Sequence) and assumptions_payload:
        ctx.assumptions = [str(item) for item in assumptions_payload if item not in (None, "")]
    elif hydrated_intent and getattr(hydrated_intent, "assumptions", None) and not ctx.assumptions:
        ctx.assumptions = list(hydrated_intent.assumptions or [])

def _build_schema_clarifier_request(decision: ClarifierDecision, session_id: str) -> Optional[ClarifyRequestModel]:
    if not decision.slot or not decision.question:
        return None
    options = decision.options or []
    default_option = options[0] if options else None
    input_type = "single" if options else "free"
    return ClarifyRequestModel(
        slot=decision.slot,
        question=decision.question,
        type=input_type,
        options=options,
        default=default_option,
        reason=decision.reason or "Required by the schema clarifier.",
        required=True,
        request_id=str(uuid.uuid4()),
        proposed=None,
        proposed_confidence=None,
        session_id=session_id,
    )


def _followup_to_clarify_request(followup: FollowUpModel, session_id: str) -> ClarifyRequestModel:
    options = list(followup.suggestions or [])
    allow_custom = followup.allow_custom if followup.allow_custom is not None else True
    if options:
        input_type = "single"
    else:
        input_type = "free"
    default_option = options[0] if options else None
    reason = followup.reason or "Additional information is required to continue."
    return ClarifyRequestModel(
        slot=followup.slot,
        question=followup.prompt,
        type=input_type,
        options=options,
        default=default_option if not allow_custom else None,
        reason=reason,
        required=True,
        request_id=str(uuid.uuid4()),
        proposed=default_option if allow_custom and default_option else None,
        proposed_confidence=None,
        session_id=session_id,
        allow_custom=allow_custom,
    )


def _compose_intent_from_resolution(
    query: str,
    configs: Mapping[str, Any],
    resolution: IntentResolutionModel,
    *,
    assumptions: Sequence[str] = (),
) -> IntentModel:
    """Merge structured slot resolution output with heuristic signals into a runtime IntentModel."""
    heuristic_model = detect_intent(query, configs)

    selection = getattr(resolution, "intent", None)
    intent_key = getattr(selection, "key", None)
    if not intent_key:
        intent_key = heuristic_model.intent_key
    confidence = getattr(selection, "confidence", None)
    if confidence is None:
        confidence = heuristic_model.confidence

    slots_detected: Dict[str, Any] = {}
    for slot_name, status in (resolution.slots or {}).items():
        if not isinstance(status, SlotStatusModel):
            continue
        if status.value is None:
            continue
        slots_detected[slot_name] = status.value

    slots_detected["original_query"] = query
    normalized_slots = post_process_slots(slots_detected, query, configs)

    reasoning = resolution.notes or heuristic_model.intent_reasoning or ""

    combined_assumptions = list(heuristic_model.assumptions or [])
    for assumption in assumptions:
        if assumption not in combined_assumptions:
            combined_assumptions.append(assumption)

    return IntentModel(
        intent_key=intent_key,
        confidence=confidence or 0.0,
        slots_detected=normalized_slots,
        assumptions=combined_assumptions,
        clarifications_suggested=list(heuristic_model.clarifications_suggested or []),
        possible_intents=list(heuristic_model.possible_intents or []),
        intent_reasoning=reasoning,
    )


def _normalize_metric_slots(resolution: IntentResolutionModel) -> None:
    if not isinstance(resolution, IntentResolutionModel):
        return

    def _normalize(slot_name: str) -> None:
        slot_state = resolution.slots.get(slot_name)
        if slot_state is None:
            return
        value = slot_state.value
        has_value = False
        if isinstance(value, (list, tuple, set)):
            has_value = any(item is not None for item in value)
        elif value not in (None, "", []):
            has_value = True
        if slot_state.status == "missing" and has_value:
            resolution.slots[slot_name] = slot_state.model_copy(update={"status": "defaulted"})
        updated = resolution.slots.get(slot_name)
        if updated and updated.status != "missing":
            resolution.followups = [
                followup
                for followup in list(resolution.followups or [])
                if getattr(followup, "slot", None) != slot_name
            ]

    _normalize("metric")
    _normalize("metrics")


def _build_slot_assumptions(slots: Mapping[str, SlotStatusModel]) -> List[str]:
    assumptions: List[str] = []
    for slot_name, status in (slots or {}).items():
        if not isinstance(status, SlotStatusModel):
            continue
        if status.status == "defaulted" and status.value is not None:
            assumptions.append(f"{slot_name} defaulted to {status.value}")
        elif status.status == "assumed":
            assumptions.append(f"{slot_name} assumed ({status.status})")
    return assumptions


def _apply_plan_metric_defaults(
    ctx: PlannerPhaseContext,
    plan: Optional[QueryPlanModel],
    *,
    configs: Mapping[str, Any],
) -> List[str]:
    """
    Ensure metric slots are populated when the query plan already specifies concrete metrics.

    Returns the normalized metric list that was applied, or an empty list if no updates occurred.
    """
    if plan is None:
        return []
    plan_metrics = list(getattr(plan, "metrics", []) or [])
    if not plan_metrics:
        return []

    normalized_metrics = normalize_metrics(plan_metrics, configs)
    if not normalized_metrics:
        return []

    intent_key = getattr(getattr(ctx, "intent", None), "intent_key", None)
    if intent_key in {"margins_vs_peers", "margin_growth_vs_peers"}:
        margin_choice = detect_margin_choice_from_metrics(normalized_metrics)
        if margin_choice is None:
            return []

    updated = False
    metric_status = ctx.slot_statuses.get("metric")
    metric_value_missing = True
    if isinstance(metric_status, SlotStatusModel):
        value = metric_status.value
        if isinstance(value, str) and value.strip():
            metric_value_missing = False
        elif isinstance(value, (list, tuple, set)) and any(v for v in value):
            metric_value_missing = False
        elif value is not None and not isinstance(value, (list, tuple, set, str)):
            metric_value_missing = False

    if metric_value_missing:
        suggestions = list(metric_status.suggestions or []) if isinstance(metric_status, SlotStatusModel) else []
        if not suggestions:
            suggestions = normalized_metrics
        reason = None
        allow_custom = True
        if isinstance(metric_status, SlotStatusModel):
            reason = metric_status.reason
            if metric_status.allow_custom is not None:
                allow_custom = metric_status.allow_custom
        ctx.slot_statuses["metric"] = SlotStatusModel(
            status="defaulted",
            value=normalized_metrics[0],
            reason=reason or "Metric auto-filled from plan defaults.",
            suggestions=suggestions,
            allow_custom=allow_custom,
        )
        ctx.intent_resolution.slots["metric"] = ctx.slot_statuses["metric"]
        updated = True

    metrics_status = ctx.slot_statuses.get("metrics")
    metrics_value_missing = True
    if isinstance(metrics_status, SlotStatusModel):
        value = metrics_status.value
        if isinstance(value, (list, tuple, set)) and any(value):
            metrics_value_missing = False
        elif isinstance(value, str) and value.strip():
            metrics_value_missing = False
        elif value not in (None, "", []):
            metrics_value_missing = False

    if metrics_value_missing:
        suggestions = list(metrics_status.suggestions or []) if isinstance(metrics_status, SlotStatusModel) else []
        if not suggestions:
            suggestions = normalized_metrics
        reason = None
        allow_custom = True
        if isinstance(metrics_status, SlotStatusModel):
            reason = metrics_status.reason
            if metrics_status.allow_custom is not None:
                allow_custom = metrics_status.allow_custom
        ctx.slot_statuses["metrics"] = SlotStatusModel(
            status="defaulted",
            value=normalized_metrics,
            reason=reason or "Metrics auto-filled from plan defaults.",
            suggestions=suggestions,
            allow_custom=allow_custom,
        )
        ctx.intent_resolution.slots["metrics"] = ctx.slot_statuses["metrics"]
        updated = True

    if updated:
        if ctx.intent_resolution.followups:
            ctx.intent_resolution.followups = [
                followup for followup in ctx.intent_resolution.followups if followup.slot not in {"metric", "metrics"}
            ]
        ctx.slot_followups = [followup for followup in ctx.slot_followups if followup.slot not in {"metric", "metrics"}]

    return normalized_metrics if updated else []


def _request_allows_custom(request: ClarifyRequestModel) -> bool:
    allow_custom = getattr(request, "allow_custom", None)
    if allow_custom is not None:
        return bool(allow_custom)
    return not (request.type == "single" and request.options)


def _clarify_request_to_followup(request: ClarifyRequestModel) -> FollowUpModel:
    allow_custom = _request_allows_custom(request)
    return FollowUpModel(
        slot=request.slot,
        prompt=request.question,
        suggestions=list(request.options or []),
        allow_custom=allow_custom,
        reason=request.reason or None,
    )


def _upsert_slot_status(
    ctx: PlannerPhaseContext,
    slot: str,
    *,
    status: str,
    value: Any,
    reason: Optional[str] = None,
    suggestions: Optional[Sequence[str]] = None,
    allow_custom: Optional[bool] = None,
) -> SlotStatusModel:
    normalized_value = value
    if status == "filled":
        if slot == "timeframe":
            normalized_tf = normalize_timeframe(value, '', CONFIGS.__dict__, origin='clarification')
            if normalized_tf:
                normalized_value = normalized_tf
        elif slot in {"metric", "metrics"}:
            normalized_metrics = normalize_metrics(value, CONFIGS.__dict__)
            if slot == "metric":
                if normalized_metrics:
                    normalized_value = normalized_metrics[0]
            else:
                if normalized_metrics:
                    normalized_value = normalized_metrics

    existing = ctx.slot_statuses.get(slot)
    merged_suggestions: List[str] = []
    if existing and existing.suggestions:
        merged_suggestions.extend(existing.suggestions)
    if suggestions:
        for item in suggestions:
            if item not in merged_suggestions:
                merged_suggestions.append(item)
    resolved_reason = (
        reason
        if reason is not None
        else (existing.reason if existing else None)
    )
    resolved_allow_custom = (
        allow_custom
        if allow_custom is not None
        else (existing.allow_custom if existing is not None else None)
    )
    slot_model = SlotStatusModel(
        status=status,  # type: ignore[arg-type]
        value=normalized_value,
        reason=resolved_reason,
        suggestions=merged_suggestions,
        allow_custom=resolved_allow_custom,
    )
    ctx.slot_statuses[slot] = slot_model
    if ctx.intent_resolution is not None:
        ctx.intent_resolution.slots[slot] = slot_model
    return slot_model


def _refresh_followups(ctx: PlannerPhaseContext, requests: Sequence[ClarifyRequestModel]) -> None:
    followups = [_clarify_request_to_followup(request) for request in requests]
    ctx.slot_followups = list(followups)
    if ctx.intent_resolution is not None:
        ctx.intent_resolution.followups = list(followups)


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

    def _maybe_emit_fresh_lane_event(
        self,
        ctx: PlannerPhaseContext,
        lane: str,
        status: str,
        *,
        reason: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if self._suppress_fresh_pipeline:
            return None
        if not getattr(ctx, "force_full_fresh_pipeline", False):
            return None
        status_map: Dict[str, str] = getattr(ctx, "_fresh_lane_status", {})
        if not hasattr(ctx, "_fresh_lane_status"):
            setattr(ctx, "_fresh_lane_status", status_map)
        previous = status_map.get(lane)
        if previous == status:
            return None
        if status == "started" and previous in {"started", "completed"}:
            return None
        if previous == "completed" and status == "failed":
            return None
        status_map[lane] = status
        message = f"{lane.title()} lane {status}"
        event = EventEmitter.progress(f"fresh_{lane}_{status}", message)
        data = event.setdefault("data", {})
        data["lane"] = lane
        data["status"] = status
        data["fresh_pipeline"] = True
        data["reasoning_effort"] = FRESH_RUN_REASONING_EFFORT
        data["ts"] = datetime.utcnow().isoformat()
        if reason:
            data["reason"] = reason
        telemetry.fresh_pipeline_lane(
            lane=lane,
            status=status,
            session_id=getattr(ctx, "session_id", None),
            flow=getattr(self, "flow_label", None),
            reasoning_effort=FRESH_RUN_REASONING_EFFORT,
        )
        return event

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
        lane_for_fresh: Optional[str] = None
        if tool_name.startswith("web_retriever"):
            lane_for_fresh = "web"
        elif tool_name == "stock_tracker" or tool_name.startswith("market_question"):
            lane_for_fresh = "stock"
        if lane_for_fresh:
            if status in {"completed", "complete", "success"}:
                marker = self._maybe_emit_fresh_lane_event(ctx, lane_for_fresh, "completed")
            elif status in {"failed", "error", "cancelled"}:
                marker = self._maybe_emit_fresh_lane_event(ctx, lane_for_fresh, "failed")
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
            return _accessory_tool_adapters()
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

    def _collect_tool_deltas_now(self, tool_state: Optional[Dict[str, Any]], ctx: Optional[PlannerPhaseContext] = None) -> List[Dict[str, Any]]:
        deltas: List[Dict[str, Any]] = []
        if not tool_state or not tool_state.get("active", False):
            return deltas
        queue: asyncio.Queue = tool_state["queue"]
        while True:
            try:
                event = queue.get_nowait()
            except QueueEmpty:
                break
            if event is _TOOL_QUEUE_SENTINEL:
                tool_state["active"] = False
                runtime = tool_state.get("runtime")
                if isinstance(runtime, ToolParallelRuntime):
                    runtime.active = False
                break
            deltas.append(self._mark_delta_event(event, ctx))
        return deltas

    async def _drain_tool_state_async(
        self,
        tool_state: Optional[Dict[str, Any]],
        ctx: Optional[PlannerPhaseContext] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not tool_state or not tool_state.get("active", False):
            return
        queue: asyncio.Queue = tool_state["queue"]
        while tool_state.get("active", False):
            event = await queue.get()
            if event is _TOOL_QUEUE_SENTINEL:
                tool_state["active"] = False
                runtime = tool_state.get("runtime")
                if isinstance(runtime, ToolParallelRuntime):
                    runtime.active = False
                break
            yield self._mark_delta_event(event, ctx)
        for pending in self._collect_tool_deltas_now(tool_state, ctx):
            yield pending

    async def _emit_post_analysis_accessories(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        mode_config = get_mode_config(ctx.flow_mode)
        if mode_config.accessories_in_critical_path:
            return

        lane_refresh_flags = dict(getattr(ctx, "lane_refresh_required", {}) or {})
        web_refresh_required = bool(lane_refresh_flags.get("web", True))
        market_refresh_required = bool(lane_refresh_flags.get("market", True))

        accessory_tools: Set[str] = set()
        if web_refresh_required:
            accessory_tools.add("web_retriever")
        if market_refresh_required:
            accessory_tools.add("stock_tracker")

        existing_results = getattr(ctx, "tool_parallel_results", []) or []
        completed_tools = {result.get("tool") for result in existing_results}
        pending_tools = [tool for tool in accessory_tools if tool not in completed_tools]
        if pending_tools:
            adapter_lookup = {adapter.name: adapter for adapter in get_default_tool_adapters()}
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
        async for event in _classification_phase(self, ctx):
            yield event

    async def run_intent(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in _intent_phase(self, ctx):
            yield event

    async def run_clarification(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in _clarification_phase(self, ctx):
            yield event

    async def run_plan(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in _plan_phase(self, ctx):
            yield event

    async def run_sql_pipeline(
        self,
        ctx: PlannerPhaseContext,
        *,
        intent: IntentModel,
        plan: QueryPlanModel,
        candidate_templates: List[Dict[str, Any]],
        selected_template_id: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
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
        receipt = ctx.tool_receipts.get("sql_chain")
        if receipt:
            receipt.status = "running"
            receipt.reused = False
            if not receipt.input_hash:
                receipt.input_hash = _hash_payload(input_payload)
            receipt.attempts = 0
            receipt.error = None
            receipt.output_hash = None
        else:
            receipt = ToolInvocationReceipt(
                tool="sql_chain",
                status="running",
                attempts=0,
                input_hash=_hash_payload(input_payload),
            )
        start_time = time.time()
        ctx.tool_receipts["sql_chain"] = receipt

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
        receipt = ctx.tool_receipts.get("chart_builder")
        if ctx.reused_chart:
            if receipt:
                receipt.status = "reused"
                receipt.reused = True
                receipt.error = None
            else:
                receipt = ToolInvocationReceipt(
                    tool="chart_builder",
                    status="reused",
                    attempts=0,
                    input_hash=_hash_payload(input_payload),
                    reused=True,
                )
            ctx.tool_receipts["chart_builder"] = receipt
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
        if receipt:
            receipt.status = "running"
            receipt.reused = False
            receipt.error = None
            if not receipt.input_hash:
                receipt.input_hash = _hash_payload(input_payload)
        else:
            receipt = ToolInvocationReceipt(
                tool="chart_builder",
                status="running",
                attempts=0,
                input_hash=_hash_payload(input_payload),
            )
        chart_start = time.time()
        ctx.tool_receipts["chart_builder"] = receipt
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
        chart_design = _generate_chart_design(intent.intent_key, plan, data, spec)
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
        receipt = ctx.tool_receipts.get("analysis_synthesis")
        refresh_mode = getattr(ctx, "analysis_refresh_mode", "full")
        if refresh_mode == "light":
            if receipt:
                receipt.status = "reused"
                receipt.reused = True
                receipt.error = None
                receipt.metadata["refresh_mode"] = "light"
            else:
                receipt = ToolInvocationReceipt(
                    tool="analysis_synthesis",
                    status="reused",
                    attempts=0,
                    reused=True,
                    metadata={"refresh_mode": "light"},
                )
                ctx.tool_receipts["analysis_synthesis"] = receipt
            ctx.reused_analysis = True
            event = _build_reused_analysis_event(self.flow_mode, ctx)
            if event:
                event["data"]["refresh_mode"] = "light"
                yield self._annotate_revision(event, ctx)
            return
        if ctx.reused_analysis:
            if receipt:
                receipt.status = "reused"
                receipt.reused = True
                receipt.error = None
            else:
                receipt = ToolInvocationReceipt(
                    tool="analysis_synthesis",
                    status="reused",
                    attempts=0,
                    reused=True,
                )
            ctx.tool_receipts["analysis_synthesis"] = receipt
            return
        if receipt:
            receipt.status = "running"
            receipt.reused = False
            receipt.error = None
            receipt.output_hash = None
            receipt.metadata["refresh_mode"] = refresh_mode
        else:
            receipt = ToolInvocationReceipt(
                tool="analysis_synthesis",
                status="running",
                attempts=0,
                metadata={"refresh_mode": refresh_mode},
            )
        ctx.tool_receipts["analysis_synthesis"] = receipt
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
        tool_runtime: Optional[ToolParallelRuntime] = None
        tool_state: Optional[Dict[str, Any]] = None
        is_session_follow_up = bool(getattr(ctx, "session_follow_up", False))
        fresh_run = not is_session_follow_up
        if fresh_run and ctx.follow_up_route != FollowUpRoute.FULL_PIPELINE:
            ctx.follow_up_route = FollowUpRoute.FULL_PIPELINE
        ctx.force_full_fresh_pipeline = fresh_run
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
            forced_refresh = dict(getattr(ctx, "lane_refresh_required", {}) or {})
            forced_refresh["web"] = True
            forced_refresh["market"] = True
            ctx.lane_refresh_required = forced_refresh
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
            if should_run_parallel:
                tool_runtime = self._start_tool_parallelism(
                    ctx,
                    adapters=fanout_adapters,
                )
                tool_state = {"queue": tool_runtime.queue, "active": True, "runtime": tool_runtime}
                for tool_event in self._collect_tool_deltas_now(tool_state, ctx):
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

            start_sql = self._maybe_emit_fresh_lane_event(ctx, "sql", "started")
            if start_sql:
                yield start_sql
            try:
                async for event in stream_sql_lane(
                    self,
                    ctx=ctx,
                    registry=registry,
                    executed=executed,
                    tool_state=tool_state,
                    run_sql_lane=run_sql_lane,
                ):
                    yield event
            except Exception:
                fail_sql = self._maybe_emit_fresh_lane_event(ctx, "sql", "failed")
                if fail_sql:
                    yield fail_sql
                raise
            else:
                complete_sql = self._maybe_emit_fresh_lane_event(ctx, "sql", "completed")
                if complete_sql:
                    yield complete_sql

            accessory_lanes: Tuple[str, ...] = ()
            if ctx.force_full_fresh_pipeline:
                accessory_lanes = ("web", "stock")
                for lane in accessory_lanes:
                    start_lane = self._maybe_emit_fresh_lane_event(ctx, lane, "started")
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
                    fail_lane = self._maybe_emit_fresh_lane_event(ctx, lane, "failed")
                    if fail_lane:
                        yield fail_lane
                raise

            if stock_only_run:
                ctx.reused_stock = False
                if tool_state and tool_state.get("active", False):
                    async for tool_event in self._drain_tool_state_async(tool_state, ctx):
                        yield tool_event
                else:
                    ad_hoc_runtime = self._start_tool_parallelism(
                        ctx,
                        adapters=(StockTrackerAdapter(),),
                        concurrency_override=1,
                    )
                    ad_hoc_state = {"queue": ad_hoc_runtime.queue, "active": True, "runtime": ad_hoc_runtime}
                    try:
                        async for tool_event in self._drain_tool_state_async(ad_hoc_state, ctx):
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

            start_chart = self._maybe_emit_fresh_lane_event(ctx, "chart", "started")
            if start_chart:
                yield start_chart
            try:
                async for event in stream_chart_lane(
                    self,
                    ctx=ctx,
                    registry=registry,
                    executed=executed,
                    tool_state=tool_state,
                    run_chart_lane=run_chart_lane,
                ):
                    yield event
            except Exception:
                fail_chart = self._maybe_emit_fresh_lane_event(ctx, "chart", "failed")
                if fail_chart:
                    yield fail_chart
                raise
            else:
                complete_chart = self._maybe_emit_fresh_lane_event(ctx, "chart", "completed")
                if complete_chart:
                    yield complete_chart

            start_analysis = self._maybe_emit_fresh_lane_event(ctx, "analysis", "started")
            if start_analysis:
                yield start_analysis
            try:
                async for event in stream_analysis_lane(
                    self,
                    ctx=ctx,
                    registry=registry,
                    executed=executed,
                    tool_state=tool_state,
                    mode_config=mode_config,
                ):
                    yield event
            except Exception:
                fail_analysis = self._maybe_emit_fresh_lane_event(ctx, "analysis", "failed")
                if fail_analysis:
                    yield fail_analysis
                raise
            else:
                complete_analysis = self._maybe_emit_fresh_lane_event(ctx, "analysis", "completed")
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
    hydrate_from_snapshot = (
        bool(ctx.session_follow_up)
        or self.follow_up_route != FollowUpRoute.FULL_PIPELINE
        or prefetched_snapshot is not None
    )
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
    if not ctx.revision_snapshot:
        ctx.revision_targets = set()
        ctx.revision_hint_active = False
    else:
        ctx.revision_targets = set(revision_targets)
        ctx.revision_hint_active = hint_active
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
    if ctx.revision_context and ctx.revision_context.receipts:
        ctx.tool_receipts.update(ctx.revision_context.receipts)
    _apply_revision_context_hints(ctx)
    return ctx


async def _classification_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
    timed_emitter = ctx.timed_emitter
    timed_emitter.start_step("classification")
    classification_started_ts = datetime.utcnow().isoformat()
    classifier_provider = (os.getenv("ANALYTICS_CLASSIFIER_PROVIDER") or "gemini").strip().lower()
    if classifier_provider not in {"gemini", "openai"}:
        classifier_provider = "gemini"
    if classifier_provider == "gemini":
        model_name = os.getenv("GEMINI_CLASSIFIER_MODEL", "gemini-2.5-flash-lite")
    else:
        model_name = os.getenv("OPENAI_CLASSIFIER_MODEL", "gpt-5-nano-2025-08-07")
    yield {
        "event": "classification_started",
        "data": {
            "message": "Starting query classification...",
            "model": model_name,
            "provider": classifier_provider,
            "step": "classification",
            "ts": classification_started_ts,
        },
    }

    resolver_mode = _FLOW_MODE_TO_RESOLVER_MODE.get(ctx.flow_mode, "single_agent")
    prior_slot_values = {
        slot: status.value
        for slot, status in (ctx.slot_statuses or {}).items()
        if isinstance(status, SlotStatusModel) and status.value is not None
    }
    slot_task = asyncio.create_task(
        resolve_intent_slots_async(
            ctx.query,
            CONFIGS.__dict__,
            mode=resolver_mode,
            context_slots=prior_slot_values or None,
            session_id=ctx.session_id,
        ),
        name=f"intent-slots::{ctx.session_id}",
    )
    classifier_task = asyncio.create_task(
        _run_classifier_with_timeout(ctx, model_name, classifier_provider),
        name=f"classifier::{ctx.session_id}",
    )
    try:
        classification, slot_resolution = await asyncio.gather(classifier_task, slot_task)
    except Exception:
        classifier_task.cancel()
        slot_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await classifier_task
            await slot_task
        raise

    ctx.intent_resolution = slot_resolution
    ctx.classification = classification
    ctx.is_financial_query = bool(getattr(classification, "is_financial_query", False))
    ctx.artifacts.classification = ClassificationArtifactModel(
        query=ctx.query,
        category=getattr(classification, "topic_category", None),
        confidence=getattr(classification, "confidence", None),
        is_financial=getattr(classification, "is_financial_query", None),
        model=model_name,
        raw=classification.model_dump(),
    )
    self._capture_artifacts(ctx)
    reasoning_message = f"LLM classified topic '{classification.topic_category}'"
    yield {
        "event": "classification_reasoning",
        "data": {
            "thinking": reasoning_message,
            "confidence": classification.confidence,
            "category": classification.topic_category,
            "step": "classification",
            "ts": datetime.utcnow().isoformat(),
        },
    }
    classification_elapsed = timed_emitter.end_step("classification")
    classification_complete = {
        "event": "classification_complete",
        "data": {
            "is_financial": ctx.is_financial_query,
            "category": classification.topic_category,
            "confidence": classification.confidence,
            "ts": datetime.utcnow().isoformat(),
        },
    }
    if classification_elapsed:
        classification_complete["data"]["elapsed_ms"] = classification_elapsed
    yield classification_complete
    if not ctx.is_financial_query and not getattr(ctx, "is_revision_follow_up", False):
        polite_default = (
            "I'm focused on financial analytics questions. Please rephrase with a company, metric, or ticker so I can help."
        )
        decline_message = classification.polite_decline_message or polite_default
        if len(decline_message) > 200:
            decline_message = decline_message[:197] + "..."
        decline_notice = {
            "event": "classification_declined",
            "data": {
                "message": decline_message,
                "category": classification.topic_category,
                "confidence": classification.confidence,
                "ts": datetime.utcnow().isoformat(),
            },
        }
        yield decline_notice
        final_event = {
            "event": "final_answer",
            "data": {
                "message": decline_message,
                "confidence": classification.confidence,
                "category": classification.topic_category,
                "ts": datetime.utcnow().isoformat(),
            },
        }
        if getattr(classification, "suggested_rephrase", None):
            final_event["data"]["suggested_rephrase"] = classification.suggested_rephrase
        yield final_event
        planner_payload = _build_planner_result_payload(ctx)
        result_event = EventEmitter.result("planner_result", planner_payload)
        result_event["event"] = "planner_result"
        result_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield result_event
        workflow_summary = {
            "status": "off_topic",
            "category": classification.topic_category,
            "total_elapsed_ms": int((time.time() - ctx.workflow_start) * 1000),
        }
        workflow_complete = EventEmitter.result("workflow_complete", workflow_summary)
        workflow_complete["event"] = "workflow_complete"
        workflow_complete["data"]["ts"] = datetime.utcnow().isoformat()
        yield workflow_complete

async def _intent_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
    timed_emitter = ctx.timed_emitter
    intent_progress = EventEmitter.progress("intent_detection", "Detecting intent...")
    intent_progress["data"]["ts"] = datetime.utcnow().isoformat()
    yield intent_progress
    timed_emitter.start_step("intent_detection")
    yield {
        "event": "intent_detection_started",
        "data": {
            "message": "Analyzing query intent...",
            "ts": datetime.utcnow().isoformat(),
        },
    }
    intent_start = time.time()
    slot_resolution = ctx.intent_resolution
    if slot_resolution is None:
        resolver_mode = _FLOW_MODE_TO_RESOLVER_MODE.get(ctx.flow_mode, "single_agent")
        prior_slot_values = {
            slot: status.value
            for slot, status in (ctx.slot_statuses or {}).items()
            if isinstance(status, SlotStatusModel) and status.value is not None
        }
        slot_resolution = await resolve_intent_slots_async(
            ctx.query,
            CONFIGS.__dict__,
            mode=resolver_mode,
            context_slots=prior_slot_values or None,
            session_id=ctx.session_id,
        )
    ctx.intent_resolution = slot_resolution
    _normalize_metric_slots(slot_resolution)
    ctx.intent_resolution = slot_resolution
    ctx.slot_statuses = slot_resolution.slots
    ctx.slot_followups = list(slot_resolution.followups or [])

    slot_assumptions = _build_slot_assumptions(ctx.slot_statuses)
    intent = _compose_intent_from_resolution(
        ctx.query,
        CONFIGS.__dict__,
        slot_resolution,
        assumptions=slot_assumptions,
    )
    ctx.intent = intent
    ctx.assumptions = list(intent.assumptions or [])

    intent_elapsed = timed_emitter.end_step("intent_detection")
    resolver_status = "structured"
    if isinstance(slot_resolution.notes, str) and "fell back" in slot_resolution.notes.lower():
        resolver_status = "fallback"

    ctx.provisional_plan = build_query_plan(intent, CONFIGS.__dict__)
    ctx.template = choose_template(intent, ctx.provisional_plan, CONFIGS.__dict__)

    plan_metric_defaults = _apply_plan_metric_defaults(
        ctx,
        ctx.provisional_plan,
        configs=CONFIGS.__dict__,
    )
    if plan_metric_defaults:
        slot_assumptions = _build_slot_assumptions(ctx.slot_statuses)
        intent = _compose_intent_from_resolution(
            ctx.query,
            CONFIGS.__dict__,
            ctx.intent_resolution,
            assumptions=slot_assumptions,
        )
        ctx.intent = intent
        ctx.assumptions = list(intent.assumptions or [])

    slot_status_payload = {
        slot: {
            "status": status.status,
            "value": status.value,
            "reason": status.reason,
            "suggestions": list(status.suggestions or []),
            "allow_custom": status.allow_custom,
        }
        for slot, status in ctx.slot_statuses.items()
    }

    clarification_sources: Set[str] = set()
    if ctx.slot_followups:
        clarification_sources.add("structured_resolver")
    if resolver_status == "fallback":
        clarification_sources.add("heuristic_fallback")

    schema_decision: Optional[ClarifierDecision] = None
    if SCHEMA_CLARIFIER_ENABLED and ctx.template is not None:
        try:
            schema_decision = await asyncio.to_thread(
                decide_schema_clarification,
                intent,
                ctx.provisional_plan,
                session_id=ctx.session_id,
                template_id=intent.intent_key or (ctx.template.get("name") if isinstance(ctx.template, dict) else None),
                slot_statuses=ctx.slot_statuses,
            )
        except Exception as exc:
            logger.exception("[SCHEMA_CLARIFIER] decision failed: %s", exc)
            schema_decision = ClarifierDecision(action="fallback", missing_slots=[])
    elif SCHEMA_CLARIFIER_ENABLED:
        schema_decision = ClarifierDecision(action="fallback", missing_slots=[])

    ctx.clarifier_agent_invoked = bool(schema_decision)
    ctx.schema_clarifier_decision = schema_decision
    intent_raw = intent.model_dump()
    try:
        intent_raw["slot_resolution"] = slot_resolution.model_dump()
    except Exception:  # pragma: no cover - defensive
        intent_raw["slot_resolution"] = {}
    schema_requires_clarification = bool(schema_decision and getattr(schema_decision, "action", None) == "request")
    if SCHEMA_CLARIFIER_ENABLED:
        clarifier_event = EventEmitter.progress(
            "schema_clarifier",
            f"Schema clarifier decision: {(schema_decision.action if schema_decision else 'disabled')}",
        )
        clarifier_event["data"].update(
            {
                "action": schema_decision.action if schema_decision else "disabled",
                "missing_slots": schema_decision.missing_slots if schema_decision else [],
                "enabled": True,
                "ts": datetime.utcnow().isoformat(),
            }
        )
        if schema_decision and schema_decision.slot:
            clarifier_event["data"]["slot"] = schema_decision.slot
        yield clarifier_event
        completion_action = schema_decision.action if schema_decision else "disabled"
        if completion_action in {"skip", "fallback", "disabled"}:
            yield EventEmitter.complete(
                "schema_clarifier",
                f"Schema clarifier {completion_action}",
            )

    clarifier_request: Optional[ClarifyRequestModel] = None
    if schema_decision and schema_decision.action == "skip":
        official_clarifications: List[ClarifyRequestModel] = []
    else:
        official_clarifications = compute_required_clarifications(
            intent, ctx.provisional_plan, ctx.template, CONFIGS.__dict__
        )
        if official_clarifications:
            clarification_sources.add("structured_resolver")
        if schema_decision and schema_decision.action == "clarify":
            clarifier_request = _build_schema_clarifier_request(schema_decision, ctx.session_id)
            if clarifier_request:
                official_clarifications = [clarifier_request] + [
                    request for request in official_clarifications if request.slot != clarifier_request.slot
                ]
                clarification_sources.add("schema_clarifier")
    slot_followup_requests: List[ClarifyRequestModel] = [
        _followup_to_clarify_request(followup, ctx.session_id) for followup in ctx.slot_followups
    ]
    if slot_followup_requests:
        clarification_sources.add("structured_resolver")
    if slot_followup_requests:
        existing_slots = {request.slot for request in slot_followup_requests}
        remaining_requests = [
            request for request in official_clarifications if request.slot not in existing_slots
        ]
        official_clarifications = slot_followup_requests + remaining_requests
    deduped_requests: List[ClarifyRequestModel] = []
    seen_slots: set[str] = set()
    for request in official_clarifications:
        if request.slot in seen_slots:
            continue
        seen_slots.add(request.slot)
        deduped_requests.append(request)
    for request in deduped_requests:
        existing_status = ctx.slot_statuses.get(request.slot)
        allow_custom_flag = _request_allows_custom(request)
        status_name = existing_status.status if existing_status else "missing"
        value = existing_status.value if existing_status else None
        _upsert_slot_status(
            ctx,
            request.slot,
            status=status_name,
            value=value,
            reason=request.reason,
            suggestions=request.options,
            allow_custom=allow_custom_flag,
        )
    _refresh_followups(ctx, deduped_requests)
    slot_followup_payload = [
        {
            "slot": followup.slot,
            "prompt": followup.prompt,
            "suggestions": list(followup.suggestions or []),
            "allow_custom": followup.allow_custom,
            "reason": followup.reason,
        }
        for followup in ctx.slot_followups
    ]
    ctx.clarifications = deduped_requests
    ctx.assumptions = list(ctx.assumptions or [])
    ctx.clarification_sources = clarification_sources
    ctx.clarification_rounds = 0
    clarifications_required_flag = bool(deduped_requests) or schema_requires_clarification
    ctx.artifacts.intent = IntentArtifactModel(
        query=ctx.query,
        intent_key=getattr(intent, "intent_key", None),
        confidence=getattr(intent, "confidence", None),
        slots=dict(getattr(intent, "slots_detected", {}) or {}),
        clarifications_needed=clarifications_required_flag,
        low_confidence=getattr(intent, "low_confidence", None),
        raw=intent_raw,
    )
    self._capture_artifacts(ctx)
    clarifications_needed = bool(deduped_requests)
    confidence_sufficient = (intent.confidence or 0.0) >= 0.8

    log_intent_resolution(
        intent_key=intent.intent_key,
        confidence=intent.confidence,
        slot_statuses=slot_status_payload,
        slot_followups=slot_followup_payload,
        elapsed_ms=intent_elapsed or int((time.time() - intent_start) * 1000),
        session_id=ctx.session_id,
        flow=ctx.flow_mode.value if isinstance(ctx.flow_mode, FlowMode) else str(ctx.flow_mode),
        resolver_status=resolver_status,
        clarification_sources=sorted(clarification_sources),
    )

    intent_complete = {
        "event": "intent_detection_complete",
        "data": {
            "intent_key": intent.intent_key,
            "confidence": intent.confidence,
            "slots_detected": intent.slots_detected,
            "slot_statuses": slot_status_payload,
            "slot_followups": slot_followup_payload,
            "clarification_sources": sorted(clarification_sources),
            "resolver_notes": slot_resolution.notes,
            "ts": datetime.utcnow().isoformat(),
            "elapsed_ms": int((time.time() - intent_start) * 1000),
        },
    }
    if intent_elapsed:
        intent_complete["data"]["elapsed_ms"] = intent_elapsed
    yield intent_complete

    if clarifications_needed:
        intent_status_event = EventEmitter.intent_draft(
            confidence=intent.confidence,
            clarifications_needed=True,
            clarifications_count=len(deduped_requests),
        )
    else:
        intent_status_event = EventEmitter.intent_decided(
            key=intent.intent_key,
            confidence=intent.confidence,
            clarifications_needed=False,
        )
        if not confidence_sufficient:
            intent_status_event["data"]["low_confidence"] = True
        if schema_decision:
            intent_status_event["data"]["schema_clarifier_action"] = schema_decision.action
            if schema_decision.missing_slots:
                intent_status_event["data"]["schema_clarifier_missing"] = schema_decision.missing_slots

    intent_status_event["data"]["slot_statuses"] = slot_status_payload
    intent_status_event["data"]["slot_followups"] = slot_followup_payload
    intent_status_event["data"]["clarification_sources"] = sorted(clarification_sources)
    intent_status_event["data"]["ts"] = datetime.utcnow().isoformat()
    if intent_elapsed:
        intent_status_event["data"]["elapsed_ms"] = intent_elapsed
    yield intent_status_event

async def _clarification_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
    intent = ctx.intent
    provisional_plan = ctx.provisional_plan
    template = ctx.template
    if intent is None or provisional_plan is None or ctx.halted:
        return
    timed_emitter = ctx.timed_emitter
    session_id = ctx.session_id
    official_clarifications = list(ctx.clarifications)
    assumptions = list(ctx.assumptions)
    rounds = ctx.clarification_rounds
    all_answered_slots: set[str] = set()
    history_entries: List[Dict[str, Any]] = []
    _refresh_followups(ctx, official_clarifications)
    if official_clarifications:
        timed_emitter.start_step("clarification")
        missing_slots = [req.slot for req in official_clarifications]
        yield {
            "event": "clarification_needed",
            "data": {
                "missing_fields": missing_slots,
                "ts": datetime.utcnow().isoformat(),
            },
        }
        clarification_progress = EventEmitter.progress(
            "clarification", "Clarifying requirements..."
        )
        clarification_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield clarification_progress
        yield {
            "event": "clarification_loop_start",
            "data": {
                "total_clarifications": len(official_clarifications),
                "missing_slots": missing_slots,
                "ts": datetime.utcnow().isoformat(),
            },
        }
        while official_clarifications and rounds < 3:
            slot_request = official_clarifications[0]
            request_payload = {
                "request_id": slot_request.request_id,
                "slot": slot_request.slot,
                "question": slot_request.question,
                "type": slot_request.type,
                "options": slot_request.options,
                "default": slot_request.default,
                "proposed": slot_request.proposed,
                "proposed_confidence": slot_request.proposed_confidence,
                "reason": slot_request.reason,
                "required": slot_request.required,
                "round": rounds + 1,
                "remaining": len(official_clarifications),
            }
            clarification_event = EventEmitter.clarification_request(
                session_id, request_payload
            )
            clarification_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield clarification_event
            history_entry: Dict[str, Any] = {"request": dict(request_payload)}
            try:
                answer = await asyncio.wait_for(
                    wait_for_answer_blocking(session_id, slot_request.request_id),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                timeout_event = EventEmitter.progress(
                    "clarification_timeout",
                    f"Timeout waiting for {slot_request.slot} clarification. Using default value.",
                )
                timeout_event["data"]["ts"] = datetime.utcnow().isoformat()
                yield timeout_event
                if slot_request.default:
                    from analytics.core.types import ClarifyAnswerModel
                    answer = ClarifyAnswerModel(
                        session_id=session_id,
                        request_id=slot_request.request_id,
                        slot=slot_request.slot,
                        value=slot_request.default,
                        ts=datetime.utcnow().isoformat(),
                    )
                else:
                    official_clarifications.pop(0)
                    history_entry["response"] = {
                        "status": "timeout_no_value",
                        "slot": slot_request.slot,
                    }
                    _upsert_slot_status(
                        ctx,
                        slot_request.slot,
                        status="missing",
                        value=None,
                        reason=slot_request.reason,
                        suggestions=slot_request.options,
                        allow_custom=_request_allows_custom(slot_request),
                    )
                    _refresh_followups(ctx, official_clarifications)
                    history_entries.append(history_entry)
                    continue
            if answer:
                is_valid = validate_clarification_answer(answer, slot_request)
                if is_valid:
                    ack_event = EventEmitter.clarification_ack(
                        session_id, slot_request.request_id, answer.value
                    )
                    ack_event["data"].update(
                        {
                            "slot": slot_request.slot,
                            "ts": datetime.utcnow().isoformat(),
                        }
                    )
                    slot_status = _upsert_slot_status(
                        ctx,
                        slot_request.slot,
                        status="filled",
                        value=answer.value,
                        reason=slot_request.reason,
                        suggestions=slot_request.options,
                        allow_custom=_request_allows_custom(slot_request),
                    )
                    ack_event["data"]["slot_status"] = slot_status.model_dump()
                    yield ack_event
                    intent, provisional_plan, merge_assumptions = await merge_answers(
                        intent, provisional_plan, [answer], CONFIGS.__dict__
                    )
                    assumptions.extend(merge_assumptions)
                    history_entry["response"] = {
                        "status": "accepted",
                        "slot": answer.slot,
                        "value": answer.value,
                    }
                    template = choose_template(
                        intent, provisional_plan, CONFIGS.__dict__
                    )
                    new_clarifications = compute_required_clarifications(
                        intent, provisional_plan, template, CONFIGS.__dict__
                    )
                    remaining_original = official_clarifications[1:]
                    all_answered_slots.add(answer.slot)
                    combined_requests: List[ClarifyRequestModel] = []
                    for new_req in new_clarifications:
                        if new_req.slot not in all_answered_slots and all(
                            new_req.slot != existing.slot for existing in combined_requests
                        ):
                            combined_requests.append(new_req)
                    for orig_req in remaining_original:
                        if (
                            orig_req.slot not in all_answered_slots
                            and all(orig_req.slot != existing.slot for existing in combined_requests)
                        ):
                            combined_requests.append(orig_req)
                    official_clarifications = combined_requests
                    _refresh_followups(ctx, official_clarifications)
                    rounds += 1
                else:
                    error_message = get_validation_error_message(answer, slot_request)
                    error_event = EventEmitter.progress(
                        "clarification_error",
                        error_message or f"Invalid value for {slot_request.slot}: {answer.value}",
                    )
                    error_event["data"]["ts"] = datetime.utcnow().isoformat()
                    yield error_event
                    official_clarifications = official_clarifications[1:]
                    _upsert_slot_status(
                        ctx,
                        slot_request.slot,
                        status="missing",
                        value=None,
                        reason=error_message or slot_request.reason,
                        suggestions=slot_request.options,
                        allow_custom=_request_allows_custom(slot_request),
                    )
                    _refresh_followups(ctx, official_clarifications)
                    history_entry["response"] = {
                        "status": "rejected",
                        "slot": answer.slot,
                        "value": answer.value,
                        "error": error_message,
                    }
            else:
                official_clarifications = official_clarifications[1:]
                history_entry["response"] = {
                    "status": "no_answer",
                    "slot": slot_request.slot,
                }
                _upsert_slot_status(
                    ctx,
                    slot_request.slot,
                    status="missing",
                    value=None,
                    reason=slot_request.reason,
                    suggestions=slot_request.options,
                    allow_custom=_request_allows_custom(slot_request),
                )
                _refresh_followups(ctx, official_clarifications)
            if history_entry not in history_entries:
                history_entries.append(history_entry)
        clarification_elapsed = timed_emitter.end_step("clarification")
        resolved_event = EventEmitter.intent_resolved(
            key=intent.intent_key,
            confidence=intent.confidence,
            rounds=rounds,
        )
        resolved_event["data"].update(
            {
                "assumptions": assumptions,
                "ts": datetime.utcnow().isoformat(),
            }
        )
        if clarification_elapsed:
            resolved_event["data"]["elapsed_ms"] = clarification_elapsed
        yield resolved_event
        pending_slots = sorted(
            {req.slot for req in official_clarifications if getattr(req, "slot", None)}
        )
        yield {
            "event": "clarification_complete",
            "data": {
                "rounds": rounds,
                "missing_slots": pending_slots,
                "ts": datetime.utcnow().isoformat(),
            },
        }
    else:
        yield {
            "event": "clarification_skipped",
            "data": {
                "reason": "All required slots satisfied",
                "ts": datetime.utcnow().isoformat(),
            },
        }
    ctx.intent = intent
    ctx.provisional_plan = provisional_plan
    ctx.template = template
    ctx.assumptions = assumptions
    ctx.clarification_rounds = rounds
    ctx.clarifications = official_clarifications

    remaining_missing = _auto_fill_missing_slots(ctx, assumptions)
    if remaining_missing:
        regenerated_requests: List[ClarifyRequestModel] = []
        for slot_name in remaining_missing:
            status_model = ctx.slot_statuses.get(slot_name)
            suggestions = list(status_model.suggestions or []) if status_model else []
            allow_custom = True
            if status_model and status_model.allow_custom is not None:
                allow_custom = status_model.allow_custom
            elif suggestions:
                allow_custom = False
            input_type = "single" if suggestions and not allow_custom else "free"
            default_option = suggestions[0] if suggestions and not allow_custom else None
            question_text = (
                status_model.reason
                if status_model and status_model.reason and status_model.reason.endswith("?")
                else f"Which {slot_name.replace('_', ' ')} should we use?"
            )
            regenerated_requests.append(
                ClarifyRequestModel(
                    slot=slot_name,
                    question=question_text,
                    type=input_type,
                    options=suggestions,
                    default=default_option,
                    reason=(
                        status_model.reason
                        if status_model and status_model.reason
                        else "This slot is required to continue the analysis."
                    ),
                    required=True,
                    request_id=str(uuid.uuid4()),
                    proposed=(
                        status_model.value
                        if status_model and status_model.value is not None and status_model.status in {"assumed", "defaulted"}
                        else None
                    ),
                    proposed_confidence=None,
                    session_id=ctx.session_id,
                )
            )
        ctx.clarifications = regenerated_requests
        _refresh_followups(ctx, regenerated_requests)
        ctx.halted = True
        ctx.halt_reason = "clarification_missing_slots"
        halt_event = EventEmitter.error(
            "clarification",
            "Missing required information to continue.",
            details={"missing_slots": remaining_missing},
            code="SLOTS_MISSING",
        )
        halt_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield halt_event
        workflow_summary = {
            "status": "clarification_missing_slots",
            "missing_slots": remaining_missing,
            "total_elapsed_ms": int((time.time() - ctx.workflow_start) * 1000),
        }
        workflow_complete = EventEmitter.result("workflow_complete", workflow_summary)
        workflow_complete["event"] = "workflow_complete"
        workflow_complete["data"]["ts"] = datetime.utcnow().isoformat()
        yield workflow_complete
        yield {
            "event": "clarification_failed",
            "data": {
                "rounds": rounds,
                "missing_slots": remaining_missing,
                "ts": datetime.utcnow().isoformat(),
            },
        }
        decision = ctx.schema_clarifier_decision
        clarifier_action = None
        clarifier_missing = []
        clarifier_slot = None
        if decision is not None:
            clarifier_action = getattr(decision, "action", None)
            clarifier_missing = list(getattr(decision, "missing_slots", []) or [])
            clarifier_slot = getattr(decision, "slot", None)
        else:
            clarifier_action = "request"
        ctx.artifacts.clarification = ClarificationArtifact(
            query=ctx.query,
            clarifier_action=clarifier_action,
            clarifier_missing_slots=clarifier_missing,
            clarifier_slot=clarifier_slot,
            pending=[req.model_dump() for req in regenerated_requests],
            assumptions=list(assumptions),
            resolved=False,
            rounds=rounds,
            answered_slots=sorted(all_answered_slots),
            history=history_entries,
        )
        self._capture_artifacts(ctx)
        return

    if not official_clarifications:
        _refresh_followups(ctx, [])
    decision = ctx.schema_clarifier_decision
    clarifier_action = None
    clarifier_missing = []
    clarifier_slot = None
    if decision is not None:
        clarifier_action = getattr(decision, "action", None)
        clarifier_missing = list(getattr(decision, "missing_slots", []) or [])
        clarifier_slot = getattr(decision, "slot", None)
    elif official_clarifications:
        clarifier_action = "request"
    else:
        clarifier_action = "not_required"
    ctx.artifacts.clarification = ClarificationArtifact(
        query=ctx.query,
        clarifier_action=clarifier_action,
        clarifier_missing_slots=clarifier_missing,
        clarifier_slot=clarifier_slot,
        pending=[req.model_dump() for req in official_clarifications],
        assumptions=list(assumptions),
        resolved=not official_clarifications,
        rounds=rounds,
        answered_slots=sorted(all_answered_slots),
        history=history_entries,
    )
    self._capture_artifacts(ctx)

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


def _auto_fill_missing_slots(ctx: PlannerPhaseContext, assumptions: List[str]) -> List[str]:
    assumption_lookup: Dict[str, str] = {}
    for assumption in assumptions:
        if not isinstance(assumption, str):
            continue
        parts = assumption.split(":", 1)
        if len(parts) != 2:
            continue
        key, value = parts
        assumption_lookup[key.strip().lower()] = value.strip()

    remaining_missing: List[str] = []
    for slot_name, status in (ctx.slot_statuses or {}).items():
        if not isinstance(status, SlotStatusModel):
            continue
        if status.status != "missing":
            continue
        slot_label = slot_name.replace("_", " ")
        assumption_key = f"using {slot_label}".lower()
        assumed_value = assumption_lookup.get(assumption_key)
        if assumed_value:
            status.status = "assumed"
            status.value = assumed_value
            if not status.reason:
                status.reason = "Auto-filled from existing assumptions."
            ctx.slot_statuses[slot_name] = status
            continue
        default_value: Optional[str] = None
        if slot_name == "timeframe":
            if status.suggestions:
                default_value = status.suggestions[0]
            else:
                default_value = "last_5_years"
        elif slot_name == "metric":
            if status.suggestions:
                default_value = status.suggestions[0]
        elif slot_name == "comparison":
            intent_tickers: List[str] = []
            if ctx.intent and isinstance(ctx.intent.slots_detected, dict):
                intent_raw_tickers = ctx.intent.slots_detected.get("tickers")
                if isinstance(intent_raw_tickers, (list, tuple, set)):
                    for value in intent_raw_tickers:
                        symbol = str(value).strip().upper()
                        if symbol and symbol not in intent_tickers and symbol != "ALL":
                            intent_tickers.append(symbol)
            if intent_tickers and len(intent_tickers) >= 2:
                default_value = "all"
            elif status.suggestions:
                default_value = status.suggestions[0]
        if default_value:
            status.status = "defaulted"
            status.value = default_value
            if not status.reason:
                status.reason = "Auto-filled due to missing clarification."
            ctx.slot_statuses[slot_name] = status
            assumptions.append(f"Using {slot_label}: {default_value}")
            if ctx.intent and isinstance(ctx.intent.slots_detected, dict):
                ctx.intent.slots_detected[slot_name] = default_value
            continue
        remaining_missing.append(slot_name)
    return remaining_missing












from analytics.core.intent_impl.normalization import normalize_timeframe, normalize_metrics








