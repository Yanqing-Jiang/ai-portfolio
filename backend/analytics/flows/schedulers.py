# --- Analytics Function/Class Map ---
# Class: FlowMode
#   Role: Handles FlowMode logic for analytics.flows.schedulers.
#   Called from: analytics.agent_orchestrator.agent_runtime, analytics.agent_orchestrator.event_bus, analytics.flows.agents_stream_bridge, analytics.flows.instrumentation, +15 more
#   Collaborators: Internal helpers only
#   Why: Keeps analytics.flows.schedulers from duplicating FlowMode behavior across flows.
# Class: ModeConfig
#   Role: Handles ModeConfig logic for analytics.flows.schedulers.
#   Called from: analytics.flows.planner.analysis_lane
#   Collaborators: dataclasses.dataclass, dataclasses.field
#   Why: Keeps analytics.flows.schedulers from duplicating ModeConfig behavior across flows.
# Class: FlowStage
#   Role: Describe a logical phase within an analytics flow.
#   Called from: Internal to analytics.flows.schedulers
#   Collaborators: dataclasses.dataclass
#   Why: Supports downstream analytics workflows that rely on FlowStage.
# Class: FlowSchedule
#   Role: Container describing the ordered stages for a flow mode.
#   Called from: Internal to analytics.flows.schedulers
#   Collaborators: dataclasses.dataclass
#   Why: Supports downstream analytics workflows that rely on FlowSchedule.
# Class: FlowStageIndex
#   Role: Mapping helpers for translating events back to their stages.
#   Called from: analytics.flows.instrumentation
#   Collaborators: dataclasses.dataclass
#   Why: Supports downstream analytics workflows that rely on FlowStageIndex.
# Function: _core_stages
#   Role: Handles core stages logic for analytics.flows.schedulers.
#   Called from: Internal to analytics.flows.schedulers
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.schedulers from duplicating core stages behavior across flows.
# Function: get_mode_config
#   Role: Handles get mode config logic for analytics.flows.schedulers.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner_executor, analytics.flows.single_agent_tools, tests.analytics.test_planner_ledger, +1 more
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.schedulers from duplicating get mode config behavior across flows.
# Function: get_mode_schedule
#   Role: Handles get mode schedule logic for analytics.flows.schedulers.
#   Called from: tests.analytics.test_planner_ledger, tests.analytics.test_planner_schedulers
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.schedulers from duplicating get mode schedule behavior across flows.
# Function: describe_mode_schedule
#   Role: Handles describe mode schedule logic for analytics.flows.schedulers.
#   Called from: analytics.scripts.schedule_replay, tests.analytics.test_planner_schedulers
#   Invokes: analytics.flows.schedulers.get_mode_schedule
#   Why: Keeps analytics.flows.schedulers from duplicating describe mode schedule behavior across flows.
# Function: build_stage_index
#   Role: Create lookup dictionaries for a mode's schedule.
#   Called from: Internal to analytics.flows.schedulers
#   Invokes: analytics.flows.schedulers.get_mode_schedule, analytics.flows.schedulers.FlowStageIndex
#   Why: Supports downstream analytics workflows that rely on build_stage_index.
# Function: get_stage_index
#   Role: Handles get stage index logic for analytics.flows.schedulers.
#   Called from: analytics.flows.instrumentation, tests.analytics.test_planner_ledger, tests.analytics.test_planner_schedulers
#   Invokes: functools.lru_cache, analytics.flows.schedulers.build_stage_index
#   Why: Keeps analytics.flows.schedulers from duplicating get stage index behavior across flows.
# Function: resolve_stage
#   Role: Lookup a FlowStage from the cached index.
#   Called from: analytics.flows.instrumentation, tests.analytics.test_planner_schedulers
#   Invokes: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on resolve_stage.
# Function: _merge_schedule_badges
#   Role: Handles merge schedule badges logic for analytics.flows.schedulers.
#   Called from: Internal to analytics.flows.schedulers
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.schedulers from duplicating merge schedule badges behavior across flows.
# Function: _inject_schedule
#   Role: Handles inject schedule logic for analytics.flows.schedulers.
#   Called from: Internal to analytics.flows.schedulers
#   Invokes: analytics.flows.schedulers._merge_schedule_badges
#   Why: Keeps analytics.flows.schedulers from duplicating inject schedule behavior across flows.
# Function: apply_mode_metadata
#   Role: Annotate an SSE payload with mode metadata.
#   Called from: analytics.agent_orchestrator.agent_runtime, analytics.agent_orchestrator.event_bus, analytics.flows.agents_stream_bridge, analytics.flows.multi_agent, +5 more
#   Invokes: analytics.flows.schedulers.get_mode_config, analytics.flows.schedulers.get_mode_schedule, analytics.flows.schedulers._inject_schedule, analytics.flows.schedulers.get_stage_index, +1 more
#   Why: Supports downstream analytics workflows that rely on apply_mode_metadata.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, Mapping, Optional, Tuple


class FlowMode(str, Enum):
    DIRECT = "direct"
    SINGLE_AGENT = "single_agent"
    MULTI_AGENT = "multi_agent"


@dataclass(frozen=True)
class ModeConfig:
    name: FlowMode
    parallelism_enabled: bool
    accessories_in_critical_path: bool
    deterministic_badge: str
    accessory_strategy: str
    allow_hedging: bool
    delta_accessories: bool
    concurrency: Dict[str, int] = field(default_factory=dict)
    retry_ceiling: Optional[int] = None
    supervisor_model: Optional[str] = None


_MODE_CONFIGS: Mapping[FlowMode, ModeConfig] = {
    FlowMode.DIRECT: ModeConfig(
        name=FlowMode.DIRECT,
        parallelism_enabled=False,
        accessories_in_critical_path=False,
        deterministic_badge="Deterministic",
        accessory_strategy="post_analysis",
        allow_hedging=False,
        delta_accessories=True,
        concurrency={},
        retry_ceiling=None,
        supervisor_model=None,
    ),
    FlowMode.SINGLE_AGENT: ModeConfig(
        name=FlowMode.SINGLE_AGENT,
        parallelism_enabled=True,
        accessories_in_critical_path=True,
        deterministic_badge="Concurrent",
        accessory_strategy="pre_analysis_fanout",
        allow_hedging=False,
        delta_accessories=True,
        concurrency={},
        retry_ceiling=2,
        supervisor_model="gpt-5-mini-2025-08-07",
    ),
    FlowMode.MULTI_AGENT: ModeConfig(
        name=FlowMode.MULTI_AGENT,
        parallelism_enabled=True,
        accessories_in_critical_path=True,
        deterministic_badge="Supervisor",
        accessory_strategy="specialist_parallel",
        allow_hedging=True,
        delta_accessories=True,
        concurrency={"sql_web": 2, "chart_parallel": 1, "supervisor_summary": 1},
        retry_ceiling=2,
        supervisor_model="gpt-5-mini-2025-08-07",
    ),
}


@dataclass(frozen=True)
class FlowStage:
    """Describe a logical phase within an analytics flow."""

    key: str
    label: str
    parallel_group: str
    allows_parallel: bool
    steps: Tuple[str, ...] = ()
    accessories: Tuple[str, ...] = ()
    hedged_tools: Tuple[str, ...] = ()
    emits: Tuple[str, ...] = ()
    description: str = ""

    def summary(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "parallel_group": self.parallel_group,
            "allows_parallel": self.allows_parallel,
            "steps": list(self.steps),
            "accessories": list(self.accessories),
            "hedged_tools": list(self.hedged_tools),
            "emits": list(self.emits),
            "description": self.description,
        }


@dataclass(frozen=True)
class FlowSchedule:
    """Container describing the ordered stages for a flow mode."""

    mode: FlowMode
    stages: Tuple[FlowStage, ...]
    default_parallelism: bool
    accessory_strategy: str
    hedging_enabled: bool

    def summary(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "default_parallelism": self.default_parallelism,
            "accessory_strategy": self.accessory_strategy,
            "hedging_enabled": self.hedging_enabled,
            "stages": [stage.summary() for stage in self.stages],
        }


@dataclass(frozen=True)
class FlowStageIndex:
    """Mapping helpers for translating events back to their stages."""

    schedule: FlowSchedule
    events_to_stage: Dict[str, FlowStage]
    steps_to_stage: Dict[str, FlowStage]


def _core_stages(*stages: FlowStage) -> Tuple[FlowStage, ...]:
    return stages


DIRECT_SCHEDULE = FlowSchedule(
    mode=FlowMode.DIRECT,
    default_parallelism=False,
    accessory_strategy=_MODE_CONFIGS[FlowMode.DIRECT].accessory_strategy,
    hedging_enabled=_MODE_CONFIGS[FlowMode.DIRECT].allow_hedging,
    stages=_core_stages(
        FlowStage(
            key="classification",
            label="Classification",
            parallel_group="core_sequential",
            allows_parallel=False,
            steps=("classification",),
            emits=(
                "classification",
                "classification_started",
                "classification_reasoning",
                "classification_complete",
                "classification_fallback",
                "final_answer",
                "schema_clarifier",
                "schema_clarifier_result",
            ),
            description="Classify the user prompt and gate the rest of the pipeline.",
        ),
        FlowStage(
            key="intent",
            label="Intent & Planning",
            parallel_group="core_sequential",
            allows_parallel=False,
            steps=("intent_detection", "clarification"),
            emits=(
                "plan_and_select_template",
                "intent_detection_started",
                "intent_detection_complete",
                "clarification",
                "clarification_progress",
                "clarification_request",
                "clarification_resolved",
                "clarification_timeout",
                "clarification_skipped",
                "intent_finalized",
                "criteria_ready",
                "plan_built",
                "schema_validation",
            ),
            description="Detects user intent and compiles the initial SQL plan.",
        ),
        FlowStage(
            key="sql",
            label="SQL Build & Execute",
            parallel_group="core_sequential",
            allows_parallel=False,
            steps=("sql_compilation", "sql_execution"),
            emits=(
                "sql_execution",
                "sql_validation",
                "sql_compilation",
                "sql_compilation_started",
                "sql_compiled",
                "sql_generated",
                "sql_validated",
                "execution_stats",
                "sql_attempts",
                "sql_ready",
            ),
            description="Generates SQL and executes it sequentially.",
        ),
        FlowStage(
            key="chart",
            label="Chart Spec + Dataset",
            parallel_group="core_sequential",
            allows_parallel=False,
            steps=("chart_generation",),
            emits=("chart_generation", "chart_planned", "chart_spec_ready", "chart_generated", "chart_ready"),
            description="Builds the chart spec and dataset sequentially.",
        ),
        FlowStage(
            key="analysis",
            label="Narrative Analysis",
            parallel_group="core_sequential",
            allows_parallel=False,
            steps=("analysis_generation", "analysis_revision", "follow_up_route"),
            emits=(
                "analysis_generation",
                "analysis_chunk",
                "analysis_streaming",
                "analysis_complete",
                "follow_up_route",
                "workflow_complete",
                "analysis_ready",
            ),
            description="Streams the TL;DR analysis sequentially.",
        ),
        FlowStage(
            key="accessories_post",
            label="Accessories (Post Analysis)",
            parallel_group="post_accessories",
            allows_parallel=False,
            steps=("web_search",),
            accessories=("web_retriever", "stock_tracker"),
            emits=(
                "tool_parallel_start",
                "tool_parallel_result",
                "tool_parallel_complete",
                "web_research_agent",
                "tool_execution",
                "stock_ready",
                "web_ready",
            ),
            description="Runs optional accessories after analysis to preserve determinism.",
        ),
    ),
)

SINGLE_AGENT_SCHEDULE = FlowSchedule(
    mode=FlowMode.SINGLE_AGENT,
    default_parallelism=True,
    accessory_strategy=_MODE_CONFIGS[FlowMode.SINGLE_AGENT].accessory_strategy,
    hedging_enabled=_MODE_CONFIGS[FlowMode.SINGLE_AGENT].allow_hedging,
    stages=_core_stages(
        FlowStage(
            key="classification",
            label="Classification",
            parallel_group="core_sequential",
            allows_parallel=False,
            steps=("classification",),
            emits=("classification", "classification_started", "classification_complete", "schema_clarifier", "schema_clarifier_result"),
            description="Sequential classification to seed the agent context.",
        ),
        FlowStage(
            key="intent",
            label="Intent & Planning",
            parallel_group="core_sequential",
            allows_parallel=False,
            steps=("intent_detection", "clarification"),
            emits=(
                "plan_and_select_template",
                "intent_detection_started",
                "intent_detection_complete",
                "clarification",
                "clarification_progress",
                "clarification_request",
                "clarification_resolved",
                "clarification_timeout",
                "clarification_skipped",
                "intent_finalized",
                "criteria_ready",
                "plan_built",
                "schema_validation",
            ),
            description="Intent, clarifications, and SQL template choice remain sequential.",
        ),
        FlowStage(
            key="accessories_pre_analysis",
            label="Accessories (Pre Analysis Fan-out)",
            parallel_group="tool_fanout",
            allows_parallel=True,
            steps=("web_search",),
            accessories=("web_retriever_cached", "web_retriever_live", "stock_tracker"),
            hedged_tools=("web_retriever_cached", "web_retriever_live"),
            emits=(
                "tool_parallel_start",
                "tool_parallel_result",
                "tool_parallel_complete",
                "tool_fanout",
                "web_research_agent",
                "tool_execution",
                "stock_ready",
                "web_ready",
            ),
            description="Agent fan-out for accessories occurs in parallel before analysis and can overlap SQL warm-up.",
        ),
        FlowStage(
            key="sql",
            label="SQL Build & Execute",
            parallel_group="core_sequential",
            allows_parallel=False,
            steps=("sql_compilation", "sql_execution"),
            emits=(
                "sql_compilation",
                "sql_execution",
                "sql_validation",
                "sql_compilation_started",
                "sql_compiled",
                "sql_generated",
                "sql_validated",
                "execution_stats",
                "sql_ready",
            ),
            description="SQL stages run sequentially before tool fan-out.",
        ),
        FlowStage(
            key="chart",
            label="Chart Spec + Dataset",
            parallel_group="chart_build",
            allows_parallel=False,
            steps=("chart_generation",),
            emits=("chart_generation", "chart_planned", "chart_spec_ready", "chart_generated", "chart_ready"),
            description="Chart building reuses artifacts and runs sequentially after fan-out.",
        ),
        FlowStage(
            key="analysis",
            label="Narrative Analysis",
            parallel_group="analysis_stream",
            allows_parallel=False,
            steps=("analysis_generation", "analysis_revision", "follow_up_route"),
            emits=(
                "analysis_generation",
                "analysis_chunk",
                "analysis_streaming",
                "analysis_complete",
                "follow_up_route",
                "workflow_complete",
                "analysis_ready",
            ),
            description="Analysis stage streams once upstream artifacts complete.",
        ),
    ),
)

MULTI_AGENT_SCHEDULE = FlowSchedule(
    mode=FlowMode.MULTI_AGENT,
    default_parallelism=True,
    accessory_strategy=_MODE_CONFIGS[FlowMode.MULTI_AGENT].accessory_strategy,
    hedging_enabled=_MODE_CONFIGS[FlowMode.MULTI_AGENT].allow_hedging,
    stages=_core_stages(
        FlowStage(
            key="supervisor",
            label="Supervisor Kickoff",
            parallel_group="supervisor",
            allows_parallel=False,
            emits=(
                "agent_supervisor_started",
                "agent_turn_start",
                "agent_turn_end",
                "tool_retry",
                "agent_turn",
                "agent_reasoning",
                "agent_coordination",
            ),
            description="Supervisor agent sets up shared artifacts and objectives.",
        ),
        FlowStage(
            key="classification",
            label="Classification Specialist",
            parallel_group="specialist_sequential",
            allows_parallel=True,
            steps=("classification",),
            emits=(
                "classification",
                "classification_started",
                "classification_complete",
                "schema_clarifier",
                "schema_clarifier_result",
            ),
            description="Specialist handles classification while other tasks queue.",
        ),
        FlowStage(
            key="intent_sql",
            label="Intent + SQL Specialists",
            parallel_group="specialist_core",
            allows_parallel=True,
            steps=("intent_detection", "clarification", "sql_compilation", "sql_execution"),
            emits=(
                "intent_detection",
                "intent_detection_complete",
                "clarification",
                "clarification_progress",
                "clarification_resolved",
                "clarification_skipped",
                "clarification_timeout",
                "plan_and_select_template",
                "schema_validation",
                "sql_compilation",
                "sql_compiled",
                "sql_execution",
                "sql_generated",
                "sql_validated",
                "execution_stats",
                "sql_ready",
            ),
            description="Intent and SQL specialists coordinate under supervisor guidance.",
        ),
        FlowStage(
            key="hedged_accessories",
            label="Hedged Accessories",
            parallel_group="specialist_fanout",
            allows_parallel=True,
            steps=("web_search",),
            accessories=("web_retriever_cached", "web_retriever_live", "stock_tracker"),
            hedged_tools=("web_retriever_cached", "web_retriever_live"),
            emits=(
                "tool_parallel_start",
                "tool_parallel_result",
                "tool_parallel_complete",
                "tool_fanout",
                "tool_execution",
                "web_research_agent",
                "hedged_accessories_complete",
                "stock_ready",
                "web_ready",
            ),
            description="Supervisor launches hedged web retrievers plus stock tracker in parallel.",
        ),
        FlowStage(
            key="chart",
            label="Chart Specialist",
            parallel_group="specialist_chart",
            allows_parallel=True,
            steps=("chart_generation",),
            emits=("chart_generation", "chart_planned", "chart_spec_ready", "chart_generated", "chart_ready"),
            description="Chart specialist consumes SQL outputs and accessory deltas.",
        ),
        FlowStage(
            key="analysis",
            label="Analysis + Cohesive Result",
            parallel_group="analysis_stream",
            allows_parallel=True,
            steps=("analysis_generation", "analysis_revision", "follow_up_route"),
            emits=(
                "analysis_generation",
                "analysis_chunk",
                "analysis_streaming",
                "analysis_complete",
                "follow_up_route",
                "workflow_complete",
                "cohesive_result",
                "cohesive_result_error",
                "analysis_ready",
            ),
            description="Supervisor aggregates chart + accessory data into cohesive result.",
        ),
    ),
)

_MODE_SCHEDULES: Mapping[FlowMode, FlowSchedule] = {
    FlowMode.DIRECT: DIRECT_SCHEDULE,
    FlowMode.SINGLE_AGENT: SINGLE_AGENT_SCHEDULE,
    FlowMode.MULTI_AGENT: MULTI_AGENT_SCHEDULE,
}


def get_mode_config(mode: FlowMode) -> ModeConfig:
    try:
        return _MODE_CONFIGS[mode]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unknown flow mode: {mode}") from exc


def get_mode_schedule(mode: FlowMode) -> FlowSchedule:
    try:
        return _MODE_SCHEDULES[mode]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unknown schedule for flow mode: {mode}") from exc


def describe_mode_schedule(mode: FlowMode) -> Dict[str, Any]:
    schedule = get_mode_schedule(mode)
    return schedule.summary()


def build_stage_index(mode: FlowMode) -> FlowStageIndex:
    """Create lookup dictionaries for a mode's schedule."""
    schedule = get_mode_schedule(mode)
    events_to_stage: Dict[str, FlowStage] = {}
    steps_to_stage: Dict[str, FlowStage] = {}
    for stage in schedule.stages:
        for event_name in stage.emits:
            events_to_stage[event_name] = stage
        for step_name in stage.steps:
            steps_to_stage[step_name] = stage
    return FlowStageIndex(schedule=schedule, events_to_stage=events_to_stage, steps_to_stage=steps_to_stage)


@lru_cache(maxsize=None)
def get_stage_index(mode: FlowMode) -> FlowStageIndex:
    return build_stage_index(mode)


def resolve_stage(
    stage_index: FlowStageIndex,
    *,
    event_name: Optional[str] = None,
    step_name: Optional[str] = None,
) -> Optional[FlowStage]:
    """Lookup a FlowStage from the cached index."""
    if event_name:
        stage = stage_index.events_to_stage.get(event_name)
        if stage is not None:
            return stage
    if step_name:
        stage = stage_index.steps_to_stage.get(step_name)
        if stage is not None:
            return stage
    return None


def _merge_schedule_badges(
    badges: Dict[str, Any],
    schedule: FlowSchedule,
) -> None:
    badges.setdefault("mode_schedule", {"parallel_group": schedule.accessory_strategy})
    if schedule.hedging_enabled:
        badges.setdefault("hedging", "enabled")
    elif badges.get("hedging") == "enabled" and not schedule.hedging_enabled:
        badges.pop("hedging", None)


def _inject_schedule(event: Dict[str, Any], schedule: FlowSchedule) -> None:
    data = event.setdefault("data", {})
    event_name = event.get("event")
    schedule_key = data.setdefault("schedule", {})
    # Emit full schedule only for initial status-style events; later payloads get a compact
    # summary to avoid duplicating classification/intent metadata on every telemetry record.
    full_schedule_allowed = event_name in {"initializing", "follow_up_route", "revision_request", "revision_inputs_plan"}
    if not isinstance(schedule_key, dict):
        data["schedule"] = schedule.summary() if full_schedule_allowed else {"mode": schedule.mode.value}
        return
    if "mode" not in schedule_key:
        if full_schedule_allowed:
            schedule_key.update(schedule.summary())
        else:
            schedule_key.update({"mode": schedule.mode.value})
    elif full_schedule_allowed:
        schedule_key.setdefault("stages", schedule.summary().get("stages", []))
    badges = data.setdefault("badges", {})
    if isinstance(badges, dict):
        _merge_schedule_badges(badges, schedule)


def apply_mode_metadata(event: Dict[str, Any], mode: FlowMode) -> Dict[str, Any]:
    """Annotate an SSE payload with mode metadata."""
    if not isinstance(event, dict):
        return event
    data = event.setdefault("data", {})
    if not isinstance(data, dict):
        # Avoid mutating non-dict payloads; attach at top-level.
        event["mode"] = mode.value
        return event
    data.setdefault("mode", mode.value)
    data.setdefault("flow_mode", mode.value)
    config = get_mode_config(mode)
    badges = data.setdefault("badges", {})
    if isinstance(badges, dict):
        badges.setdefault("mode", config.deterministic_badge)
    schedule = get_mode_schedule(mode)
    _inject_schedule(event, schedule)
    data.setdefault("accessory_strategy", config.accessory_strategy)
    if config.allow_hedging and isinstance(badges, dict):
        badges.setdefault("hedging", "enabled")
    if config.delta_accessories:
        data.setdefault("supports_deltas", True)
    if config.concurrency:
        data.setdefault("parallel_limits", dict(config.concurrency))
    if config.retry_ceiling is not None:
        data.setdefault("retry_ceiling", config.retry_ceiling)
    if config.supervisor_model:
        data.setdefault("supervisor_model", config.supervisor_model)
    stage_index = get_stage_index(mode)
    stage = resolve_stage(
        stage_index,
        event_name=event.get("event") if isinstance(event.get("event"), str) else None,
        step_name=data.get("step") if isinstance(data.get("step"), str) else None,
    )
    if stage is not None:
        data.setdefault("parallel_group", stage.parallel_group)
        data.setdefault("schedule_stage", stage.key)
        data.setdefault("stage_allows_parallel", stage.allows_parallel)
    role_value = data.get("role")
    if role_value and "agent_role" not in data:
        data["agent_role"] = role_value
    run_id = data.get("run_id") or event.get("run_id")
    if run_id and "agents_run_id" not in data:
        data["agents_run_id"] = run_id
    retry_value = data.get("retry_count") or data.get("attempt")
    if retry_value is not None and "agents_retry_count" not in data:
        data["agents_retry_count"] = retry_value
    return event
