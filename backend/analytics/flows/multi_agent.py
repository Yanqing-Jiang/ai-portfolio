from __future__ import annotations

import hashlib
import json
import re
import time
import copy
import os
import asyncio
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository
from analytics.core.telemetry import analysis_chunk as log_analysis_chunk, agent_handoff, policy_decision
from analytics.services.polygon import PolygonMarketDataClient, PolygonError, fetch_daily_snapshot
from analytics.services.response_search import ResponseSearchError, perform_response_search
from .planner_executor import PlannerExecutorFlow, run_planner_executor
from .hooks import AnalyticsFlowHooks
from .tool_bundle import collect_tool_bundle
from .pipeline_tools import get_planner_tool_registry
from .chart_revision import (
    infer_analysis_revision_from_query,
    infer_chart_patch_from_query,
    is_analysis_revision_query,
    is_chart_revision_query,
)
from .task_plan import AgentTaskPlan, AgentTaskStep
from .orchestrator import (
    AgentExecutionOrchestrator,
    AgentRunContext,
    AgentResult,
    AgentSpec,
    AgentTask,
    OrchestratorContext,
)

_HASH_PREFIX = "analytics"
_MAX_FRAGMENT_COUNT = 5
_MAX_ANALYSIS_STORED = 1200


class _MultiAgentHooks(AnalyticsFlowHooks):
    def __init__(self, flow: "MultiAgentFlow", query: str, session_id: Optional[str] = None) -> None:
        self._flow = flow
        self._query = query
        self._active_session: Optional[str] = session_id

    async def on_flow_start(self, ctx: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        self._flow._prepare_context(self._query)
        if ctx.get("session_id") and not self._active_session:
            session = ctx.get("session_id")
            if isinstance(session, str) and session:
                self._active_session = session
        if False:
            yield {}

    async def before_event(self, ctx: Dict[str, Any], event: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}
        name = event.get("event")
        if name == "session_started":
            data = event.get("data") or {}
            self._active_session = data.get("session_id") or ctx.get("session_id")
            ctx["session_id"] = self._active_session
        self._flow._capture_event(event)
        start_event = self._flow._maybe_agent_turn_start(event)
        if start_event:
            yield start_event
        if name == "analysis_streaming":
            reasoning = self._flow._agent_reasoning(event, self._active_session)
            if reasoning:
                yield reasoning

    async def after_event(self, ctx: Dict[str, Any], event: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}
        end_event = self._flow._maybe_agent_turn_end(event)
        if end_event:
            yield end_event
        if (
            not self._flow._orchestrated
            and event.get("event") == "analysis_complete"
        ):
            async for orchestrated_event in self._flow._run_agent_orchestration(
                self._query,
                self._active_session,
            ):
                yield orchestrated_event
            self._flow._orchestrated = True

    async def on_flow_end(
        self,
        ctx: Dict[str, Any],
        *,
        error: Optional[BaseException] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}


def _make_identifier(session_id: Optional[str], prefix: str, payload: str) -> str:
    base = session_id or "sessionless"
    digest = hashlib.sha1(f"{base}:{prefix}:{payload}".encode("utf-8")).hexdigest()[:12]
    return f"{_HASH_PREFIX}:{prefix}:{digest}"


def _infer_tickers(query: Optional[str]) -> List[str]:
    if not query:
        return []
    tokens = set(re.findall(r"[A-Z]{2,5}", query))
    blacklist = {"WITH", "FROM", "AND", "THE"}
    return sorted(token for token in tokens if token not in blacklist)[:5]


# Web search is now owned by a specialist agent step in the plan.
# Legacy env flag removed; agent plan controls whether to run web search.


RECENCY_KEYWORDS = (
    "today",
    "latest",
    "recent",
    "news",
    "headline",
    "update",
    "guidance",
    "current",
    "filing",
    "quarter",
    "earnings",
)


WEB_SEARCH_MAX_ATTEMPTS = 2
WEB_SEARCH_BACKOFF_SECONDS = 0.6


def _needs_web_refresh(query: str, web_ctx: Dict[str, Any]) -> bool:
    normalized = (query or "").strip().lower()
    if any(keyword in normalized for keyword in RECENCY_KEYWORDS):
        return True
    cached_query = str(web_ctx.get('query') or web_ctx.get('query_terms') or '').strip().lower()
    if cached_query and cached_query != normalized:
        return True
    snippets = web_ctx.get('snippets') or []
    return not bool(snippets)


def _derive_tasks(
    planner_ctx: Dict[str, Any],
    sql_ctx: Dict[str, Any],
    analysis_ctx: Dict[str, Any],
    chart_ctx: Dict[str, Any],
    market_ctx: Dict[str, Any],
    query: str,
    *,
    web_ctx: Optional[Dict[str, Any]] = None,
) -> AgentTaskPlan:
    plan = AgentTaskPlan()
    attempts = sql_ctx.get("attempts") or []
    last_attempt = attempts[-1] if attempts else None
    if attempts:
        plan.add_step(
            "query",
            "run",
            reason="sql_attempt_summary",
            metadata={"outcome": last_attempt.get("status") if last_attempt else None},
        )
    else:
        plan.add_step("query", "skip", reason="no_sql_attempts")

    chart_revision = is_chart_revision_query(query)
    revision_patch = infer_chart_patch_from_query(query) if chart_revision else None

    analysis_ready = bool(analysis_ctx.get("final"))
    chart_ready = bool(chart_ctx.get("spec_summary")) and (sql_ctx.get("row_count", 0) > 0)
    tickers = planner_ctx.get("tickers", []) or market_ctx.get("tickers", []) or []
    market_ctx["tickers"] = tickers

    if analysis_revision:
        if analysis_revision_text:
            analysis_ctx["revision_text"] = analysis_revision_text
        plan.add_step("analyst", "run", reason="analysis_revision")
        plan.add_step("chart", "reuse", reason="analysis_revision")
        plan.add_step(
            "market",
            "skip",
            reason="analysis_revision",
            metadata={"tickers": tickers},
        )
        plan.add_step("web_research", "skip", reason="analysis_revision")
        return plan

    if chart_revision:
        if revision_patch:
            chart_ctx["revision_patch"] = revision_patch
        plan.add_step("chart", "run", reason="chart_revision")
        plan.add_step("analyst", "skip", reason="chart_revision")
        plan.add_step(
            "market",
            "skip",
            reason="chart_revision",
            metadata={"tickers": tickers},
        )
        plan.add_step("web_research", "run", reason="chart_revision")
        return plan

    plan.add_step(
        "analyst",
        "run" if analysis_ready else "skip",
        reason="analysis_ready" if analysis_ready else "analysis_not_available",
    )

    plan.add_step(
        "chart",
        "run" if chart_ready else "skip",
        reason="chart_ready" if chart_ready else "chart_not_available",
    )

    market_ready = bool(tickers) and chart_ready
    plan.add_step(
        "market",
        "run" if market_ready else "skip",
        reason="tickers_detected" if market_ready else "no_tickers",
        metadata={"tickers": tickers},
    )

    web_context = web_ctx or {}
    web_should_run = _needs_web_refresh(query, web_context)
    plan.add_step(
        "web_research",
        "run" if web_should_run else "skip",
        reason="recency_requested" if web_should_run else "cached_web_context",
    )

    return plan



    tasks.append(
        {
            'name': 'chart',
            'status': 'run' if chart_ready else 'skip',
            'reason': 'chart_ready' if chart_ready else 'chart_not_available',
        }
    )

    market_ready = bool(tickers) and chart_ready
    tasks.append(
        {
            'name': 'market',
            'status': 'run' if market_ready else 'skip',
            'reason': 'tickers_detected' if market_ready else 'no_tickers',
            'tickers': tickers,
        }
    )

    return tasks


def _task_status(tasks, name: str) -> str:
    """Return the status for a task by name regardless of container type."""
    if isinstance(tasks, AgentTaskPlan):
        iterable = tasks.steps
    else:
        iterable = tasks or []
    for task in iterable:
        if isinstance(task, AgentTaskStep):
            if task.name == name:
                return task.status
        elif task.get("name") == name:
            return str(task.get("status", "skip"))
    return "skip"


def _create_planner_bundle(
    session_id: Optional[str],
    query: str,
    planner_ctx: Dict[str, Any],
    sql_ctx: Dict[str, Any],
    chart_ctx: Dict[str, Any],
    analysis_ctx: Dict[str, Any],
    tasks: List[Dict[str, Any]],
    *,
    tool_manifest: Optional[List[Dict[str, Any]]] = None,
    tool_results: Optional[List[Dict[str, Any]]] = None,
    stock_widget: Optional[Dict[str, Any]] = None,
    web_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    attempts = sql_ctx.get('attempts') or []
    bundle = {
        'query': query,
        'intent': {
            'key': planner_ctx.get('intent_key'),
            'confidence': planner_ctx.get('confidence'),
        },
        'sql': {
            'row_count': sql_ctx.get('row_count'),
            'attempts': attempts,
            'status': sql_ctx.get('status'),
        },
        'analysis': {
            'available': bool(analysis_ctx.get('final')),
            'id': analysis_ctx.get('id'),
        },
        'chart': {
            'spec_id': chart_ctx.get('spec_id'),
            'summary': chart_ctx.get('spec_summary'),
        },
        'assets': {
            'sql_id': sql_ctx.get('id'),
            'chart_id': chart_ctx.get('spec_id'),
            'analysis_id': analysis_ctx.get('id'),
        },
        'tasks': tasks,
    }
    tickers = planner_ctx.get('tickers') or []
    if tickers:
        bundle['tickers'] = tickers
    if attempts:
        bundle['sql']['last_attempt'] = attempts[-1]
    if tool_manifest:
        bundle['tool_manifest'] = copy.deepcopy(tool_manifest)
    if tool_results:
        bundle['tool_results'] = copy.deepcopy(tool_results)
    visuals: Dict[str, Any] = {}
    if stock_widget:
        visuals['stock_widget'] = copy.deepcopy(stock_widget)
    if web_context:
        visuals['web_context'] = copy.deepcopy(web_context)
    if visuals:
        bundle['visuals'] = visuals
    serialized = json.dumps(bundle, sort_keys=True, default=str)
    bundle['id'] = _make_identifier(session_id, 'bundle', serialized)
    return bundle





async def _planner_agent(context: AgentRunContext) -> AgentResult:
    shared = context.shared
    planner_ctx = shared.setdefault('planner', {})
    sql_ctx = shared.setdefault('sql', {})
    chart_ctx = shared.setdefault('chart', {})
    analysis_ctx = shared.setdefault('analysis', {})
    market_ctx = shared.setdefault('market', {})

    shared.setdefault('query', context.query)

    plan = _derive_tasks(
        planner_ctx,
        sql_ctx,
        analysis_ctx,
        chart_ctx,
        market_ctx,
        shared.get('query', context.query),
        web_ctx=shared.setdefault('web', {}),
    )
    tasks = plan.to_dicts()
    bundle = _create_planner_bundle(
        context.session_id,
        context.query,
        planner_ctx,
        sql_ctx,
        chart_ctx,
        analysis_ctx,
        tasks,
        tool_manifest=shared.get('tool_manifest'),
        tool_results=shared.get('tool_results'),
        stock_widget=shared.get('stock_widget'),
        web_context=shared.get('web'),
    )
    agent_handoff(
        role='planner_agent',
        status='planned',
        metadata={'tasks': tasks},
        session_id=context.session_id,
        flow=shared.get('_meta', {}).get('flow_label'),
    )
    planner_ctx['tasks'] = tasks
    planner_ctx['task_plan'] = tasks
    planner_ctx['bundle'] = bundle
    return AgentResult(
        name='planner',
        output={
            'status': 'planned',
            'tasks': tasks,
            'task_plan': tasks,
            'bundle_id': bundle['id'],
            'bundle': bundle,
            'planner_result': planner_ctx.get('result'),
        },
    )



async def _query_agent(context: AgentRunContext) -> AgentResult:
    planner_output = context.dependencies.get('planner_phase')
    tasks = planner_output.output.get('tasks', []) if planner_output else []
    status = _task_status(tasks, 'query')
    sql_ctx = context.shared.get('sql', {})
    attempts = sql_ctx.get('attempts') or []
    last_attempt = attempts[-1] if attempts else None
    summary_attempts: List[Dict[str, Any]] = []
    for attempt in attempts[-3:]:
        summary_attempts.append(
            {
                'attempt': attempt.get('attempt'),
                'source': attempt.get('source'),
                'status': attempt.get('status'),
                'error_code': attempt.get('error_code'),
                'error_detail': attempt.get('error_detail'),
            }
        )
    output = {
        'status': status,
        'attempt_count': len(attempts),
        'summary': summary_attempts,
    }
    if last_attempt:
        output['last_status'] = last_attempt.get('status')
        output['last_error_code'] = last_attempt.get('error_code')
    return AgentResult(name='query', output=output)


async def _analyst_agent(context: AgentRunContext) -> AgentResult:
    planner_output = context.dependencies.get("planner_phase")
    tasks = planner_output.output.get("tasks", []) if planner_output else []
    status = _task_status(tasks, "analyst")
    analysis_ctx = context.shared.get("analysis", {})
    final_text: Optional[str] = analysis_ctx.get("final")
    summary = None
    if status in {"run", "reuse"} and final_text:
        summary = final_text
        if len(summary) > 280:
            summary = summary[:277].rstrip() + "..."
    return AgentResult(
        name="analyst",
        output={
            "status": status,
            "summary": summary,
            "word_count": len(final_text.split()) if final_text else 0,
        },
    )


async def _chart_agent(context: AgentRunContext) -> AgentResult:
    planner_output = context.dependencies.get("planner_phase")
    tasks = planner_output.output.get("tasks", []) if planner_output else []
    status = _task_status(tasks, "chart")
    chart_ctx = context.shared.get("chart", {})
    summary = chart_ctx.get("spec_summary") or {}
    spec_id = chart_ctx.get("spec_id")
    payload: Dict[str, Any] = {"status": status}
    if summary or spec_id:
        payload["chart"] = {
            "chart_type": summary.get("chart_type"),
            "series_count": summary.get("series_count"),
            "spec_id": spec_id,
        }
    return AgentResult(name="chart", output=payload)


async def _market_agent(context: AgentRunContext) -> AgentResult:
    planner_output = context.dependencies.get('planner_phase')
    tasks = planner_output.output.get('tasks', []) if planner_output else []
    status = _task_status(tasks, 'market')
    tickers = context.shared.get('planner', {}).get('tickers', [])
    market_ctx = context.shared.setdefault('market', {})
    runtime = context.shared.get('_runtime', {})
    snapshot_payload: Optional[Dict[str, Any]] = market_ctx.get('snapshot')
    error_reason: Optional[str] = None
    error_code: Optional[str] = None

    if status == 'run' and tickers:
        fetcher = runtime.get('market_fetcher')
        client = runtime.get('market_client')
        retries = market_ctx.get('retry_count', 0)
        planner_confidence = float(context.shared.get('planner', {}).get('confidence') or 0.0)
        flow_label = context.shared.get('_meta', {}).get('flow_label')
        if retries:
            threshold = 0.55 if retries == 1 else 0.7
            allowed = planner_confidence >= threshold
            policy_decision(
                policy='market_refresh_retry',
                score=planner_confidence,
                threshold=threshold,
                action='allow_retry' if allowed else 'skip_retry',
                reason=f'{retries} prior retries',
                session_id=context.session_id,
                flow=flow_label,
                metadata={'retries': retries, 'tickers': tickers},
            )
            if not allowed:
                status = 'skip'
                error_reason = 'market refresh blocked by policy'
                error_code = 'POLICY_BLOCKED'
                market_ctx['error'] = error_reason
                market_ctx['error_code'] = error_code
                market_ctx['policy_blocked'] = True
                output = {
                    'status': status,
                    'tickers': tickers,
                    'refresh': False,
                    'error': error_reason,
                    'error_code': error_code,
                    'policy_score': planner_confidence,
                    'policy_threshold': threshold,
                }
                return AgentResult(name='market', output=output)
        if fetcher and client and getattr(client, 'is_configured', False):
            try:
                snapshot = await fetcher(tickers[0], client=client)
                bars = snapshot.bars[-30:]
                snapshot_payload = {
                    'symbol': snapshot.symbol,
                    'latest_close': snapshot.latest_close,
                    'change_percent': snapshot.change_percent,
                    'bars': [{'time': bar.time, 'close': bar.close} for bar in bars],
                }
                market_ctx['snapshot'] = snapshot_payload
                market_ctx['retry_count'] = 0
                market_ctx.pop('error', None)
                market_ctx.pop('error_code', None)
            except Exception as exc:
                error_reason = str(exc)
                error_code = 'POLYGON_API_ERROR' if isinstance(exc, PolygonError) else 'MARKET_FETCH_ERROR'
                market_ctx['error'] = error_reason
                market_ctx['error_code'] = error_code
                market_ctx['retry_count'] = retries + 1
        else:
            error_reason = 'polygon_client_unconfigured'
            error_code = 'POLYGON_CLIENT_UNCONFIGURED'
            market_ctx['error'] = error_reason
            market_ctx['error_code'] = error_code
            market_ctx['retry_count'] = retries + 1
    elif status == 'reuse':
        snapshot_payload = market_ctx.get('snapshot')
        error_code = market_ctx.get('error_code')
        error_reason = market_ctx.get('error')
    else:
        market_ctx.pop('snapshot', None)
        market_ctx.pop('error', None)
        market_ctx.pop('error_code', None)
        snapshot_payload = None

    output: Dict[str, Any] = {
        'status': status,
        'tickers': tickers,
        'refresh': status == 'run',
    }
    if snapshot_payload:
        output['insights'] = snapshot_payload
    if error_reason:
        output['error'] = error_reason
        output['error_code'] = error_code or 'UNKNOWN_MARKET_ERROR'
    return AgentResult(name='market', output=output)






async def _web_research_agent(context: AgentRunContext) -> AgentResult:
    web_ctx = context.shared.setdefault('web', {})
    query = context.shared.get('query', context.query)
    session_id = context.session_id

    attempts_meta: List[Dict[str, Any]] = []

    # Always allow specialist agent to attempt web search; errors/caching handled below.
    repository = get_session_state_repository()
    snapshot = await repository.load(session_id) if session_id else None
    cached_payload = None
    if snapshot:
        cache = snapshot.tool_cache.get('web_search')
        if cache and str(cache.get('query') or '').strip().lower() == query.strip().lower():
            cached_payload = cache

    if cached_payload and not _needs_web_refresh(query, web_ctx):
        web_ctx.update(cached_payload)
        web_ctx['ready'] = True
        web_ctx['from_cache'] = True
        attempts_meta = list(cached_payload.get('attempts', attempts_meta))
        web_ctx['attempts'] = attempts_meta
        return AgentResult(
            name='web_research',
            output={
                'status': 'reuse',
                'summary': cached_payload.get('summary'),
                'snippets': cached_payload.get('snippets'),
                'from_cache': True,
                'attempts': attempts_meta,
                'attempt_count': len(attempts_meta),
            },
        )

    last_error: Optional[Exception] = None
    search_result = None
    for attempt in range(1, WEB_SEARCH_MAX_ATTEMPTS + 1):
        try:
            search_result = await perform_response_search(
                query,
                session_id=session_id,
            )
            attempts_meta.append({
                'attempt': attempt,
                'status': 'success',
                'latency_ms': search_result.latency_ms,
            })
            break
        except ResponseSearchError as exc:
            last_error = exc
            attempts_meta.append({
                'attempt': attempt,
                'status': 'error',
                'error': str(exc),
            })
            if attempt >= WEB_SEARCH_MAX_ATTEMPTS:
                web_ctx['error'] = str(exc)
                web_ctx['attempts'] = attempts_meta
                return AgentResult(
                    name='web_research',
                    output={
                        'status': 'error',
                        'error': str(exc),
                        'attempts': attempts_meta,
                        'attempt_count': len(attempts_meta),
                    },
                )
            await asyncio.sleep(min(WEB_SEARCH_BACKOFF_SECONDS * attempt, 2.0))

    if not search_result:
        error_message = str(last_error) if last_error else 'web_search_failed'
        web_ctx['error'] = error_message
        web_ctx['attempts'] = attempts_meta
        return AgentResult(
            name='web_research',
            output={
                'status': 'error',
                'error': error_message,
                'attempts': attempts_meta,
                'attempt_count': len(attempts_meta),
            },
        )

    payload = search_result.to_payload()
    payload['query'] = query
    payload['ready'] = True
    payload['from_cache'] = False
    payload['attempts'] = attempts_meta
    web_ctx.update(payload)

    if snapshot:
        snapshot.record_tool_result('web_search', payload)
        await repository.save(snapshot)

    web_ctx['attempts'] = attempts_meta

    return AgentResult(
        name='web_research',
        output={
            'status': 'run',
            'summary': payload.get('summary'),
            'snippets': payload.get('snippets'),
            'search_id': payload.get('search_id'),
            'from_cache': False,
            'attempts': attempts_meta,
            'attempt_count': len(attempts_meta),
        },
        metrics={'latency_ms': search_result.latency_ms},
    )



def _build_default_agent_registry() -> Dict[str, AgentSpec]:
    return {
        'planner': AgentSpec(
            name='planner',
            system_prompt='Plan the analytics workflow into specialist-ready tasks while keeping payloads light.',
            capabilities=('task_planning', 'sql_routing'),
            latency_budget_ms=400,
            entrypoint=_planner_agent,
        ),
        'query': AgentSpec(
            name='query',
            system_prompt='Summarize SQL attempt history and highlight retry outcomes.',
            capabilities=('sql_diagnostics',),
            latency_budget_ms=300,
            entrypoint=_query_agent,
        ),
        'analyst': AgentSpec(
            name='analyst',
            system_prompt='Summarize findings using planner context and cached notes without re-querying data.',
            capabilities=('narrative', 'context_blending'),
            latency_budget_ms=500,
            entrypoint=_analyst_agent,
        ),
        'chart': AgentSpec(
            name='chart',
            system_prompt='Convert planner data into chart metadata summaries only when required.',
            capabilities=('visualization', 'vega_lite'),
            latency_budget_ms=400,
            entrypoint=_chart_agent,
        ),
        'market': AgentSpec(
            name='market',
            system_prompt='Surface market context for planner tickers without persisting across sessions.',
            capabilities=('market_data', 'ticker_updates'),
            latency_budget_ms=400,
            entrypoint=_market_agent,
        ),
        'web_research': AgentSpec(
            name='web_research',
            system_prompt='Retrieve fresh external signals and citations for the active query.',
            capabilities=('web_search', 'context_enrichment'),
            latency_budget_ms=600,
            entrypoint=_web_research_agent,
        ),
    }





def _build_default_plan() -> List[AgentTask]:
    return [
        AgentTask(name='planner_phase', agent='planner'),
        AgentTask(name='query_phase', agent='query', depends_on=('planner_phase',)),
        AgentTask(name='analyst_phase', agent='analyst', depends_on=('planner_phase',)),
        AgentTask(name='chart_phase', agent='chart', depends_on=('planner_phase',)),
        AgentTask(name='market_phase', agent='market', depends_on=('planner_phase',)),
        AgentTask(name='web_research_phase', agent='web_research', depends_on=('planner_phase',)),
    ]





class MultiAgentFlow:
    """Coordinates specialist agents while reusing the planner-executor core."""

    AGENT_START_STEPS = {
        "intent_detection": "intent_analyst",
        "clarification": "user_liaison",
        "sql_compilation": "sql_specialist",
        "sql_validation": "risk_controller",
        "sql_execution": "data_engineer",
        "chart_generation": "viz_designer",
        "chart_revision": "viz_designer",
        "analysis_generation": "insight_reviewer",
        "analysis_revision": "insight_reviewer",
    }

    AGENT_END_EVENTS = {
        "intent_detection_complete": "intent_analyst",
        "clarification_resolved": "user_liaison",
        "clarification_skipped": "user_liaison",
        "clarification_timeout": "user_liaison",
        "sql_generated": "sql_specialist",
        "sql_validated": "risk_controller",
        "execution_stats": "data_engineer",
        "sql_attempts": "query_agent",
        "chart_generated": "viz_designer",
        "chart_patch": "viz_designer",
        "analysis_revision": "insight_reviewer",
        "analysis_complete": "insight_reviewer",
    }

    ORCHESTRATION_ROLES: Dict[str, str] = {
        "planner_phase": "planner_agent",
        "query_phase": "query_agent",
        "analyst_phase": "analyst_agent",
        "chart_phase": "chart_agent",
        "market_phase": "market_agent",
    }

    def __init__(self) -> None:
        self._planner = PlannerExecutorFlow()
        self.flow_label = "multi-agent"
        self._planner_tool_manifest = get_planner_tool_registry().describe_tools()
        self._timers: Dict[str, float] = {}
        self._agent_registry = _build_default_agent_registry()
        self._orchestrator = AgentExecutionOrchestrator(self._agent_registry)
        self._base_plan = _build_default_plan()
        self._market_client = PolygonMarketDataClient()
        self._market_fetcher = fetch_daily_snapshot
        self._session_snapshot: Optional[SessionStateSnapshot] = None
        self._shared_context: Dict[str, Any] = {}
        self._orchestrated = False

    async def _forward_with_hooks(
        self,
        stream: AsyncGenerator[Dict[str, Any], None],
        hooks: _MultiAgentHooks,
        query: str,
        session_id: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        hook_ctx: Dict[str, Any] = {"query": query, "session_id": session_id}
        try:
            async for start_event in hooks.on_flow_start(hook_ctx):
                yield start_event
            async for event in stream:
                async for pre_event in hooks.before_event(hook_ctx, event):
                    yield pre_event
                yield event
                if event.get("event") == "session_started":
                    data = event.get("data") or {}
                    hook_ctx["session_id"] = data.get("session_id", hook_ctx.get("session_id"))
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
        self, query: str, session_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        planner_events = getattr(self._planner, "events", None)
        hooks = _MultiAgentHooks(self, query, session_id=session_id)
        if callable(planner_events):
            try:
                async for event in planner_events(query, session_id=session_id, hooks=hooks):
                    yield event
                return
            except TypeError:
                planner_stream = planner_events(query, session_id=session_id)
                async for event in self._forward_with_hooks(planner_stream, hooks, query, session_id):
                    yield event
                return

        planner_stream = run_planner_executor(query, session_id=session_id)
        async for event in self._forward_with_hooks(planner_stream, hooks, query, session_id):
            yield event

    async def chart_revision(
        self,
        query: str,
        *,
        session_id: Optional[str],
        patch: Dict[str, Any],
        reason: Optional[str] = None,
        source: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if session_id is None:
            raise ValueError("chart_revision requires an existing session_id")
        hooks = _MultiAgentHooks(self, query, session_id=session_id)
        ctx = await self._planner.initialize_context(query, session_id=session_id)
        registry = get_planner_tool_registry()
        tool_stream = registry.invoke(
            "chart_revision",
            self._planner._pipeline,
            ctx,
            patch=patch,
            reason=reason,
            source=source,
        )
        async for event in self._forward_with_hooks(tool_stream, hooks, query, session_id):
            yield event

    async def analysis_revision(
        self,
        query: str,
        *,
        session_id: Optional[str],
        analysis: str,
        reason: Optional[str] = None,
        source: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if session_id is None:
            raise ValueError("analysis_revision requires an existing session_id")
        hooks = _MultiAgentHooks(self, query, session_id=session_id)
        ctx = await self._planner.initialize_context(query, session_id=session_id)
        registry = get_planner_tool_registry()
        tool_stream = registry.invoke(
            "analysis_revision",
            self._planner._pipeline,
            ctx,
            analysis=analysis,
            reason=reason,
            source=source,
        )
        async for event in self._forward_with_hooks(tool_stream, hooks, query, session_id):
            yield event

    def _prepare_context(self, query: str) -> None:
        preserved_market = self._shared_context.get('market', {})
        preserved_web = self._shared_context.get('web', {})
        self._shared_context = {
            'query': query,
            'planner': {'tickers': _infer_tickers(query)},
            'sql': {'attempts': []},
            'chart': {},
            'analysis': {'fragments': [], 'final': None},
            'market': preserved_market or {},
            'web': preserved_web or {},
            'tool_manifest': self._planner_tool_manifest,
            'tool_results': [],
            'stock_widget': None,
            'agents': {},
            '_runtime': {
                'market_fetcher': self._market_fetcher,
                'market_client': self._market_client,
            },
            '_meta': {
                'flow_label': getattr(self, 'flow_label', None),
            },
        }
        self._orchestrated = False

    def _capture_event(self, event: Dict[str, Any]) -> None:
        name = event.get("event")
        data = event.get("data") or {}
        if name == "session_started":
            session_identifier = data.get("session_id")
            if session_identifier:
                self._session_snapshot = SessionStateSnapshot(session_id=session_identifier)
            return

        planner_ctx = self._shared_context.setdefault("planner", {})
        sql_ctx = self._shared_context.setdefault("sql", {})
        analysis_ctx = self._shared_context.setdefault("analysis", {"fragments": [], "final": None})
        chart_ctx = self._shared_context.setdefault("chart", {})

        if name == "intent_detection_complete":
            planner_ctx["intent_key"] = data.get("intent_key")
            planner_ctx["confidence"] = data.get("confidence")
            if self._session_snapshot:
                self._session_snapshot.record_query(
                    self._shared_context.get("query", ""),
                    planner_ctx.get("intent_key"),
                )
            slots = data.get("slots_detected") or {}
            planner_ctx["slots"] = {k: v for k, v in slots.items() if k in {"company", "metric", "ticker"}}
            companies = slots.get("company")
            if isinstance(companies, str):
                companies = [companies]
            if isinstance(companies, list):
                planner_ctx["tickers"] = sorted(set(planner_ctx.get("tickers", [])).union({str(item) for item in companies}))[:5]
        elif name == "planner_result":
            planner_ctx["result"] = data

        elif name == "sql_generated":
            sql_text = data.get("sql") or ""
            sql_ctx["llm_used"] = data.get("llm_used")
            sql_ctx["template_fallback"] = data.get("template_fallback")
            sql_ctx["generated"] = True
            if sql_text:
                sql_ctx["id"] = _make_identifier(self._session_id, "sql", sql_text)
                self._record_snapshot(sql=sql_text)
        elif name == "sql_validated":
            sql_ctx["validated"] = data.get("ok", False)
            sql_ctx["issues"] = data.get("issues_count", 0)
        elif name == "sql_attempts":
            attempts = data.get("attempts") or []
            sql_ctx["attempts"] = attempts
            if attempts:
                sql_ctx["status"] = attempts[-1].get("status")
        elif name == "execution_stats":
            sql_ctx["row_count"] = data.get("row_count")
            sql_ctx["status"] = 'success'
        elif name == "chart_generated":
            spec = data.get("chart_spec")
            if spec is not None:
                identifier = _make_identifier(self._session_id, "chart", json.dumps(spec, sort_keys=True))
                chart_ctx["spec_id"] = identifier
                chart_ctx["spec_summary"] = {
                    "chart_type": data.get("chart_type"),
                    "series_count": len(spec.get("datasets", [])) if isinstance(spec, dict) else None,
                }
                data["chart_spec_id"] = identifier
                self._record_snapshot(chart_spec=spec)
            else:
                chart_ctx["spec_summary"] = {"chart_type": data.get("chart_type")}
        elif name == "analysis_streaming":
            fragment = data.get("partial_analysis")
            if fragment:
                fragments: List[str] = analysis_ctx.setdefault("fragments", [])
                if len(fragments) < _MAX_FRAGMENT_COUNT:
                    fragments.append(fragment[:200])
        elif name == "analysis_complete":
            final_text = data.get("analysis") or ""
            if final_text:
                truncated = final_text[:_MAX_ANALYSIS_STORED]
                analysis_ctx["final"] = truncated
                analysis_ctx["id"] = _make_identifier(self._session_id, "analysis", final_text)
                analysis_ctx["length"] = data.get("analysis_length", len(final_text))
                self._record_snapshot(analysis=final_text)
            tool_bundle = collect_tool_bundle(
                manifest=self._shared_context.get("tool_manifest"),
                results=self._shared_context.get("tool_results"),
                stock_widget=data.get("stock_widget"),
                web_context=data.get("web_context"),
            )
            if tool_bundle.get("stock_widget"):
                self._shared_context["stock_widget"] = tool_bundle["stock_widget"]
            if tool_bundle.get("web_context"):
                web_ctx = self._shared_context.setdefault("web", {})
                web_ctx.update(tool_bundle["web_context"])
            if tool_bundle and self._session_snapshot:
                self._session_snapshot.record_tool_result("visual_bundle", tool_bundle)

        elif name == "web_search":
            payload = data.get("web_context") or {}
            if payload:
                web_ctx = self._shared_context.setdefault('web', {})
                web_ctx.update(payload)
                if self._session_snapshot:
                    try:
                        self._session_snapshot.record_tool_result('web_search', payload)
                    except Exception:
                        pass
            return

        elif name == "tool_parallel_start":
            manifest = data.get("tools") or data.get("tool_manifest")
            if manifest:
                self._shared_context["tool_manifest"] = manifest
                self._shared_context["tool_results"] = []

        elif name == "tool_parallel_result":
            results_list = self._shared_context.setdefault("tool_results", [])
            results_list.append(copy.deepcopy(data))
            if len(results_list) > 10:
                del results_list[0]
            tool_name = (data.get("tool") or "").strip()
            if tool_name == "web_retriever":
                web_ctx = self._shared_context.setdefault('web', {})
                payload = data.get("payload") or {}
                metadata = data.get("metadata") or {}
                if payload:
                    web_ctx.update(payload)
                    web_ctx['ready'] = payload.get('ready', False)
                    web_ctx.setdefault('query', payload.get('query_terms'))
                elif metadata.get('summary'):
                    web_ctx.setdefault('summary', metadata.get('summary'))
                if metadata.get('cache_hit') is not None:
                    web_ctx['cache_hit'] = metadata.get('cache_hit')
                if metadata.get('summary') and not web_ctx.get('summary'):
                    web_ctx['summary'] = metadata.get('summary')
            elif tool_name == "stock_tracker":
                payload = data.get("payload") or {}
                if isinstance(payload, dict) and payload.get('ready'):
                    widget = collect_tool_bundle(results=[data]).get('stock_widget')
                    if widget:
                        self._shared_context['stock_widget'] = widget
            bundle_update = collect_tool_bundle(
                manifest=self._shared_context.get('tool_manifest'),
                results=self._shared_context.get('tool_results'),
            )
            if bundle_update.get('stock_widget'):
                self._shared_context['stock_widget'] = bundle_update['stock_widget']
            if bundle_update.get('web_context'):
                web_ctx = self._shared_context.setdefault('web', {})
                web_ctx.update(bundle_update['web_context'])

    async def _run_agent_orchestration(
        self,
        query: str,
        session_id: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        for task in self._base_plan:
            role = self.ORCHESTRATION_ROLES.get(task.name)
            if role:
                yield self._format_agent_turn(role, "start")

        context = OrchestratorContext(
            query=query,
            session_id=session_id,
            shared=self._shared_context,
        )
        results = await self._orchestrator.run(self._base_plan, context)

        planner_result = results.get("planner_phase")
        bundle = planner_result.output.get("bundle") if planner_result else None

        for task in self._base_plan:
            role = self.ORCHESTRATION_ROLES.get(task.name)
            result = results.get(task.name)
            if not role or not result:
                continue
            reasoning = self._format_reasoning(role, result)
            if reasoning:
                yield reasoning
            yield self._format_agent_turn(
                role,
                "complete",
                summary=self._result_summary(result),
                elapsed=result.elapsed_ms,
            )
            agent_output = result.output or {}
            agent_handoff(
                role=role,
                status=str(agent_output.get('status') or 'unknown'),
                elapsed_ms=result.elapsed_ms,
                handoff=','.join(task.depends_on) if getattr(task, 'depends_on', None) else None,
                retries=len(agent_output.get('attempts') or []),
                session_id=session_id,
                flow=getattr(self, 'flow_label', None),
                metadata={'summary': agent_output.get('summary'), 'tickers': agent_output.get('tickers')},
            )

        await self._persist_bundle(bundle)

    def _maybe_agent_turn_start(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if event.get("event") != "progress":
            return None
        step = (event.get("data") or {}).get("step")
        role = self.AGENT_START_STEPS.get(step)
        if not role:
            return None
        self._timers[role] = time.time()
        return {
            "event": "agent_turn",
            "data": {
                "role": role,
                "status": "start",
                "step": step,
                "ts": datetime.utcnow().isoformat(),
            },
        }

    def _maybe_agent_turn_end(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        role = self.AGENT_END_EVENTS.get(event.get("event"))
        if not role:
            return None
        start = self._timers.pop(role, None)
        elapsed = int((time.time() - start) * 1000) if start else None
        payload: Dict[str, Any] = {
            "role": role,
            "status": "complete",
            "ts": datetime.utcnow().isoformat(),
        }
        summary = self._agent_summary(role, event)
        if summary:
            payload["summary"] = summary
        if elapsed is not None:
            payload["elapsed_ms"] = elapsed
        return {"event": "agent_turn", "data": payload}

    def _agent_reasoning(self, event: Dict[str, Any], session_id: Optional[str]) -> Optional[Dict[str, Any]]:
        delta = (event.get("data") or {}).get("partial_analysis")
        if not delta:
            return None
        log_analysis_chunk(
            chunk=delta,
            step="analysis_generation",
            role="insight_reviewer",
            session_id=session_id,
            flow=getattr(self, "flow_label", None),
        )
        return {
            "event": "agent_reasoning",
            "data": {
                "role": "insight_reviewer",
                "thought": delta,
                "ts": datetime.utcnow().isoformat(),
            },
        }

    def _agent_summary(self, role: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = event.get("data") or {}
        if role == "intent_analyst":
            return {"intent_key": data.get("intent_key"), "confidence": data.get("confidence")}
        if role == "sql_specialist":
            return {"llm_used": data.get("llm_used"), "template_fallback": data.get("template_fallback")}
        if role == "risk_controller":
            return {"ok": data.get("ok"), "issues": data.get("issues_count")}
        if role == "data_engineer":
            return {"rows": data.get("row_count")}
        if role == "viz_designer":
            payload = {"chart_type": data.get("chart_type")}
            if "chart_spec_id" in data:
                payload["chart_spec_id"] = data.get("chart_spec_id")
            return payload
        if role == "insight_reviewer":
            return {"analysis_length": data.get("analysis_length")}
        return None

    def _format_agent_turn(
        self,
        role: str,
        status: str,
        *,
        summary: Optional[Dict[str, Any]] = None,
        elapsed: Optional[int] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "role": role,
            "status": status,
            "ts": datetime.utcnow().isoformat(),
        }
        if summary:
            payload["summary"] = summary
        if elapsed is not None:
            payload["elapsed_ms"] = elapsed
        return {"event": "agent_turn", "data": payload}

    def _format_reasoning(self, role: str, result: AgentResult) -> Optional[Dict[str, Any]]:
        output = result.output or {}
        thought: Optional[str] = None
        if role == "planner_agent":
            tasks = output.get("tasks") or []
            bundle_id = output.get("bundle_id")
            descriptors = [f"{item['name']}={item['status']}" for item in tasks if isinstance(item, dict)]
            pieces = ["Planner tasks"]
            if bundle_id:
                pieces.append(f"bundle={bundle_id}")
            if descriptors:
                pieces.append(", ".join(descriptors))
            thought = " | ".join(pieces)
        elif role == "query_agent":
            attempts = output.get('attempt_count')
            last_status = output.get('last_status')
            last_error = output.get('last_error_code')
            parts = []
            if attempts is not None:
                parts.append(f"attempts={attempts}")
            if last_status:
                parts.append(f"last={last_status}")
            if last_error:
                parts.append(f"error={last_error}")
            thought = " | ".join(parts) if parts else None
        elif role == "analyst_agent":
            status = output.get("status")
            summary = output.get("summary")
            thought = f"Analyst status: {status}"
            if summary:
                thought = f"Analyst ({status}) summary: {summary[:120]}"
        elif role == "chart_agent":
            status = output.get("status")
            chart = output.get("chart") or {}
            if chart.get("chart_type"):
                thought = f"Chart agent ({status}) prepared {chart['chart_type']}"
            else:
                thought = f"Chart agent status: {status}"
        elif role == "market_agent":
            status = output.get("status")
            tickers = output.get("tickers") or []
            insights = output.get("insights") or {}
            change = insights.get("change_percent")
            if change is not None and tickers:
                thought = f"Market agent ({status}) {tickers[0]} change {change:.2f}%"
            elif tickers:
                thought = f"Market agent ({status}) monitoring {', '.join(tickers[:3])}"
            else:
                thought = f"Market agent status: {status}"
        if not thought:
            return None
        return {
            "event": "agent_reasoning",
            "data": {
                "role": role,
                "thought": thought,
                "ts": datetime.utcnow().isoformat(),
            },
        }

    def _result_summary(self, result: AgentResult) -> Dict[str, Any]:
        output = result.output or {}
        summary: Dict[str, Any] = {}
        if "status" in output:
            summary["status"] = output["status"]
        if "bundle_id" in output:
            summary["bundle_id"] = output["bundle_id"]
        if "tasks" in output:
            summary["tasks"] = output["tasks"]
        if "attempt_count" in output:
            summary["attempt_count"] = output["attempt_count"]
        if "last_status" in output and output.get("last_status") is not None:
            summary["last_status"] = output["last_status"]
        if "last_error_code" in output and output.get("last_error_code") is not None:
            summary["last_error_code"] = output["last_error_code"]
        if "summary" in output and output["summary"]:
            summary["attempts"] = output["summary"]
        if "chart" in output and output["chart"]:
            summary["chart"] = output["chart"]
        if "tickers" in output and output["tickers"]:
            summary["tickers"] = output["tickers"]
        if "snippets" in output and output["snippets"]:
            summary["snippets"] = len(output["snippets"])
        if "from_cache" in output:
            summary["from_cache"] = output["from_cache"]
        insights = output.get("insights")
        if insights:
            summary["insights"] = {
                "symbol": insights.get("symbol"),
                "change_percent": insights.get("change_percent"),
                "latest_close": insights.get("latest_close"),
            }
        if output.get("error"):
            summary["error"] = output["error"]
        return summary

    async def _persist_bundle(self, bundle: Optional[Dict[str, Any]]) -> None:
        if not bundle or not self._session_snapshot:
            return
        try:
            self._session_snapshot.record_tool_result("planner_bundle", bundle)
            repository = get_session_state_repository()
            await repository.save(self._session_snapshot)
        except Exception:
            pass

    def _record_snapshot(
        self,
        *,
        sql: Optional[str] = None,
        chart_spec: Optional[Dict[str, Any]] = None,
        analysis: Optional[str] = None,
    ) -> None:
        if not self._session_snapshot:
            return
        self._session_snapshot.record_outputs(
            sql=sql,
            chart_spec=chart_spec,
            analysis=analysis,
        )

        return {
        }

    @property
    def _session_id(self) -> Optional[str]:
        return getattr(self._session_snapshot, "session_id", None)


__all__ = ["MultiAgentFlow"]

