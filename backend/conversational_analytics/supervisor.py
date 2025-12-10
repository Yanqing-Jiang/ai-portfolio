"""Supervisor + specialist orchestration for conversational analytics."""
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional
import json
import time
import asyncio

from .agent import ConversationalAnalyticsAgent, get_conversational_analytics_agent, SYSTEM_PROMPT
from .streaming import (
    agent_event,
    handoff_event,
    content_event,
    process_node_event,
    process_edge_event,
    process_update_event,
    process_clear_event,
)
from .config import settings
from .sdk_assets import (
    load_agent_prompt,
    load_project_guide,
    load_project_settings,
    should_use_sdk_assets,
)
from .memory import session_store

SupervisorPlan = List[Dict[str, Any]]


SPECIALIST_CONFIGS: Dict[str, Dict[str, Any]] = {
    "database_admin": {
        "label": "Database Admin",
        "role": "data",
        "tool_allowlist": ["query_database", "generate_analysis"],
        "plan": [
            {"id": "understand", "label": "Understand question", "status": "running"},
            {"id": "sql", "label": "Query comp_financials", "status": "pending"},
            {"id": "prepare", "label": "Prepare structured result", "status": "pending"},
            {"id": "analysis", "label": "Summarize insights", "status": "pending"},
        ],
        "prompt_suffix": (
            "You are the Database Admin specialist.\n\n"
            "ROLE: Execute SQL queries against comp_financials and return structured results.\n\n"
            "CONSTRAINTS:\n"
            "- ONLY use query_database and generate_analysis tools\n"
            "- Do NOT build charts (supervisor delegates to chart_builder)\n"
            "- Always include value_unit, tickers, and period metadata in results\n\n"
            "WORKFLOW:\n"
            "1) Understand the data request\n"
            "2) Build precise SQL for comp_financials\n"
            "3) Return structured rows with metadata for downstream use\n"
            "4) Provide data summary insights"
        ),
    },
    "chart_builder": {
        "label": "Chart Builder",
        "role": "visualization",
        "tool_allowlist": ["generate_echarts", "create_tradingview_chart", "generate_analysis"],
        "plan": [
            {"id": "understand", "label": "Understand question", "status": "running"},
            {"id": "validate", "label": "Validate data/ticker context", "status": "pending"},
            {"id": "build_chart", "label": "Build visualization", "status": "pending"},
            {"id": "annotate", "label": "Annotate chart choices", "status": "pending"},
        ],
        "prompt_suffix": (
            "You are the Chart Builder specialist.\n\n"
            "ROLE: Build visualizations using ECharts (data viz) or TradingView (price charts).\n\n"
            "CONSTRAINTS:\n"
            "- Do NOT run SQL (supervisor provides data context or use TradingView for price data)\n"
            "- Use generate_echarts for financial data visualizations (bar/line/pie/area)\n"
            "- Use create_tradingview_chart for stock price charts (candlestick/volume)\n"
            "- Choose the appropriate chart type based on the request\n\n"
            "WORKFLOW:\n"
            "1) Determine chart type: ECharts for data, TradingView for price\n"
            "2) Validate context (data rows or ticker symbol)\n"
            "3) Build polished chart with proper formatting\n"
            "4) Briefly explain chart design choices"
        ),
    },
    "news": {
        "label": "News & Sentiment",
        "role": "context",
        "tool_allowlist": ["get_news_sentiment", "web_search", "generate_analysis"],
        "plan": [
            {"id": "understand", "label": "Understand question", "status": "running"},
            {"id": "search", "label": "Search web for context", "status": "pending"},
            {"id": "fetch", "label": "Fetch news & sentiment", "status": "pending"},
            {"id": "summarize", "label": "Summarize with citations", "status": "pending"},
        ],
        "prompt_suffix": (
            "You are the News & Sentiment specialist.\n\n"
            "ROLE: Gather market context through web search and news sentiment analysis.\n\n"
            "CONSTRAINTS:\n"
            "- Use web_search for real-time market news and context\n"
            "- Use get_news_sentiment for ticker-specific sentiment analysis\n"
            "- Do NOT use SQL, TradingView, or ECharts\n"
            "- Always cite sources and provide sentiment summary\n\n"
            "WORKFLOW:\n"
            "1) Use web_search for broader market context if needed\n"
            "2) Fetch ticker-specific news and sentiment\n"
            "3) Summarize relevance with citations\n"
            "4) Provide sentiment labels and follow-up suggestions"
        ),
    },
}


def _auto_route(message: str) -> str:
    """Function: _auto_route — pick a specialist for auto mode based on user text.
    Called from: SupervisorOrchestrator.run when agent_mode is 'auto'.
    Invokes: Keyword matching to route to database_admin, chart_builder, or news.
    Purpose: Routes user requests to the most appropriate specialist."""
    text = message.lower()
    # Price/stock charts -> chart_builder (now handles TradingView)
    if any(keyword in text for keyword in ["price", "stock price", "candlestick", "ohlc", "tradingview", "volume", "stock chart"]):
        return "chart_builder"
    # News and sentiment -> news specialist
    if any(keyword in text for keyword in ["news", "headline", "sentiment", "articles", "press", "market news"]):
        return "news"
    # Explicit charting requests -> chart_builder
    if any(keyword in text for keyword in ["chart", "visualize", "plot", "graph", "bar chart", "line chart", "pie chart"]):
        return "chart_builder"
    # Data queries, comparisons, SQL -> database_admin
    if any(keyword in text for keyword in ["compare", "revenue", "margin", "growth", "dataset", "table", "query", "data", "financials"]):
        return "database_admin"
    # Default to database_admin for analytical questions
    return "database_admin"


class SupervisorOrchestrator:
    """Coordinates supervisor routing to specialists."""

    MAX_SPECIALIST_RETRIES = 2
    SPECIALIST_TIMEOUT_SECONDS = 30

    def __init__(self, base_agent: Optional[ConversationalAnalyticsAgent] = None):
        self.agent = base_agent or get_conversational_analytics_agent()
        self.use_sdk_assets = should_use_sdk_assets(settings.use_sdk_assets)
        self.project_guide = load_project_guide() if self.use_sdk_assets else None
        self.sdk_settings = load_project_settings() if self.use_sdk_assets else {}
        timeouts = self.sdk_settings.get("timeouts", {}) if self.sdk_settings else {}
        self.specialist_timeout_seconds = timeouts.get("specialist_seconds", self.SPECIALIST_TIMEOUT_SECONDS)

    def _build_prompt(self, mode: str, user_message: str) -> str:
        """Function: _build_prompt — used internally to assemble specialist prompts.
        Called from: run when routing to a given mode.
        Invokes: SYSTEM_PROMPT base text and appends specialist suffix.
        Purpose: Keeps specialist prompts concise while inheriting the global system guidance."""
        config = SPECIALIST_CONFIGS.get(mode)
        suffix = config["prompt_suffix"] if config else ""
        prompt_parts = [SYSTEM_PROMPT]
        if self.project_guide:
            prompt_parts.append(self.project_guide)
        agent_prompt = load_agent_prompt(mode) if self.use_sdk_assets else None
        if agent_prompt:
            prompt_parts.append(agent_prompt)
        else:
            prompt_parts.append(f"Specialist Mode: {mode}\n{suffix}")
        return "\n\n".join(prompt_parts)

    def _build_plan(self, mode: str) -> Optional[SupervisorPlan]:
        """Function: _build_plan — returns per-mode plan steps for UI."""
        config = SPECIALIST_CONFIGS.get(mode)
        return config["plan"] if config else None  # type: ignore

    def _allowed_tools(self, mode: str) -> List[str] | None:
        """Function: _allowed_tools — returns allowlisted tools per mode."""
        if self.use_sdk_assets:
            settings_allowlist = self.sdk_settings.get("allowlists", {}).get("agents", {}).get(mode) if self.sdk_settings else None
            if settings_allowlist:
                return list(settings_allowlist)
        config = SPECIALIST_CONFIGS.get(mode)
        tools = config["tool_allowlist"] if config else None
        if tools:
            return list(tools)
        return None

    async def run(
        self,
        message: str,
        session_id: str,
        agent_mode: str = "auto",
    ) -> AsyncGenerator[str, None]:
        """Function: run — called from conversational_analytics.routes.chat when agent_mode is provided.
        Invokes: ConversationalAnalyticsAgent.run_with_tools with prompt/tool/plan overrides.
        Purpose: Provides supervisor + specialist routing (single-hop or multi-hop) while preserving SSE streaming."""
        resolved_mode = agent_mode or "auto"
        session = session_store.get_or_create(session_id)

        # Helpers -------------------------------------------------------------
        def _compute_divergence_flag(data_payload: Dict[str, Any]) -> bool:
            """Heuristic: if numeric spread > 20% across rows, mark divergence."""
            if not data_payload:
                return False
            rows = data_payload.get("rows") or []
            if not rows:
                return False
            first_numeric = []
            for row in rows:
                if isinstance(row, dict):
                    for v in row.values():
                        if isinstance(v, (int, float)):
                            first_numeric.append(float(v))
                            if len(first_numeric) >= 50:  # cap sample
                                break
                elif isinstance(row, (list, tuple)):
                    for v in row:
                        if isinstance(v, (int, float)):
                            first_numeric.append(float(v))
                            if len(first_numeric) >= 50:
                                break
                if len(first_numeric) >= 50:
                    break
            if len(first_numeric) < 2:
                return False
            mn, mx = min(first_numeric), max(first_numeric)
            if mn <= 0:
                return (mx - mn) > 0.2 * abs(mx if mx else 1)
            return (mx / mn) >= 1.2

        def _build_chart_context_prompt(data_payload: Dict[str, Any]) -> str:
            """Embed light data context for chart builder without blowing tokens."""
            rows = data_payload.get("rows") or []
            cols = data_payload.get("columns") or []
            sample = rows[:10] if isinstance(rows, list) else []
            return (
                f"{SYSTEM_PROMPT}\n\n"
                "Specialist Mode: chart_builder\n"
                "Context: You are receiving structured data from the Database Admin. "
                "Use it to build the best chart (ECharts) or a TradingView price chart.\n"
                f"Columns: {cols}\n"
                f"Sample rows (up to 10): {json.dumps(sample, default=str)}\n"
                "Be concise; do not rerun SQL."
            )

        async def _run_specialist(
            mode: str,
            parent_node: str,
            user_message: str,
            system_override: Optional[str] = None,
        ) -> Dict[str, Any]:
            cfg = SPECIALIST_CONFIGS.get(mode, SPECIALIST_CONFIGS["database_admin"])
            prompt = system_override or self._build_prompt(mode, user_message)
            plan_steps = self._build_plan(mode)
            tools = self._allowed_tools(mode)
            node_id = f"specialist_{mode}"

            yield process_node_event(
                node_id=node_id,
                node_type="agent",
                label=cfg["label"],
                status="running",
                parent_id=parent_node,
                description=f"Specialist: {cfg['label']} ({cfg['role']})",
                data={"role": cfg["role"], "tools": tools},
            )
            yield process_edge_event(parent_node, node_id, edge_type="handoff", label="delegate", animated=True)
            yield agent_event(mode, cfg["label"], cfg["role"])
            yield content_event(f"[{cfg['label']}] ")

            output: Dict[str, Any] = {
                "data": None,
                "chart": None,
                "news": None,
                "analysis": None,
                "agent_label": cfg["label"],
                "mode": mode,
            }

            attempts = 0
            while attempts <= self.MAX_SPECIALIST_RETRIES:
                try:
                    start_time = time.monotonic()
                    async for event in self.agent.run_with_tools(
                        user_message,
                        session_id,
                        system_prompt_override=prompt,
                        tool_allowlist=tools,
                        plan_steps_override=plan_steps,
                        agent_label=cfg["label"],
                        agent_mode=mode,
                    ):
                        yield event

                        # Capture outputs
                        if event.startswith("data: "):
                            try:
                                parsed = json.loads(event[6:].strip())
                                etype = parsed.get("type")
                                pdata = parsed.get("data", {})
                                if etype == "data":
                                    output["data"] = pdata
                                elif etype == "chart":
                                    output["chart"] = pdata
                                elif etype == "news":
                                    output["news"] = pdata
                                elif etype == "tool_end" and pdata.get("tool") == "generate_analysis":
                                    output["analysis"] = pdata.get("result")
                            except json.JSONDecodeError:
                                pass

                        if time.monotonic() - start_time > self.specialist_timeout_seconds:
                            raise TimeoutError(f"{cfg['label']} timed out")

                    if output:
                        session.set_specialist_output(mode, output)
                    yield process_update_event(node_id, "completed", f"{cfg['label']} done")
                    return
                except Exception as exc:  # pragma: no cover
                    attempts += 1
                    yield process_update_event(node_id, "error", f"{cfg['label']} failed: {exc}")
                    if attempts > self.MAX_SPECIALIST_RETRIES:
                        raise
                    yield process_update_event(node_id, "running", f"Retrying {cfg['label']} ({attempts}/{self.MAX_SPECIALIST_RETRIES})")

            return  # fallback, should not reach

        # ---------------------------------------------------------------------
        # Process start
        yield process_clear_event()
        yield process_node_event(
            node_id="supervisor_root",
            node_type="agent",
            label="Supervisor",
            status="running",
            description="Analyzing request and routing to specialists",
        )
        yield agent_event("supervisor", "Supervisor", "orchestrator")

        if resolved_mode == "auto":
            yield process_node_event(
                node_id="auto_routing",
                node_type="decision",
                label="Auto Routing",
                status="running",
                parent_id="supervisor_root",
                description="Determining best specialist for this request",
            )
            yield process_edge_event("supervisor_root", "auto_routing", animated=True)
            resolved_mode = _auto_route(message)
            yield process_update_event("auto_routing", "completed", f"Selected: {resolved_mode}")

        if resolved_mode not in SPECIALIST_CONFIGS and resolved_mode != "single":
            resolved_mode = "database_admin"

        # Single agent passthrough
        if resolved_mode == "single":
            yield process_update_event("supervisor_root", "completed", "Using single agent mode")
            async for event in self.agent.run_with_tools(message, session_id):
                yield event
            return

        parent_node = "auto_routing" if agent_mode == "auto" else "supervisor_root"

        # --- Hop 1: database_admin (default for analysis flows) ---
        primary_mode = resolved_mode
        if primary_mode == "chart_builder" or primary_mode == "news":
            # User explicitly picked a specialist: single-hop
            async for event in _run_specialist(primary_mode, parent_node, message):
                yield event
            yield process_update_event("supervisor_root", "completed", "Specialist complete")
            return

        # Default: database_admin first
        db_output: Dict[str, Any] = {}
        try:
            async for event in _run_specialist("database_admin", parent_node, message):
                yield event
                if event.startswith("data: "):
                    # opportunistic capture already inside helper
                    pass
            db_output = session.get_specialist_outputs().get("database_admin", {})
        except Exception:
            # Fallback to single agent
            yield process_node_event(
                node_id="single_fallback",
                node_type="agent",
                label="Single Agent Fallback",
                status="running",
                parent_id="supervisor_root",
                description="Database Admin failed; using single agent",
            )
            yield process_edge_event("supervisor_root", "single_fallback", edge_type="handoff", animated=True)
            yield agent_event("single", "Single Agent", "fallback")
            async for event in self.agent.run_with_tools(message, session_id, agent_mode="single", agent_label="Single Agent"):
                yield event
            return

        # --- Hop 2: chart_builder with DB context ---
        # --- Hop 2 & 3 in parallel (chart + optional news) ---
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        tasks: List[asyncio.Task[None]] = []

        async def _stream_specialist_to_queue(mode: str, parent: str, user_msg: str, prompt_override: Optional[str] = None):
            try:
                async for ev in _run_specialist(mode, parent, user_msg, system_override=prompt_override):
                    await queue.put(ev)
            finally:
                await queue.put(None)

        if db_output.get("data"):
            chart_prompt = _build_chart_context_prompt(db_output["data"])
            tasks.append(asyncio.create_task(_stream_specialist_to_queue("chart_builder", "supervisor_root", message, chart_prompt)))

        divergence_flag = _compute_divergence_flag(db_output.get("data", {}))
        if divergence_flag:
            tasks.append(asyncio.create_task(_stream_specialist_to_queue("news", "supervisor_root", message)))

        if tasks:
            done_count = 0
            while done_count < len(tasks):
                ev = await queue.get()
                if ev is None:
                    done_count += 1
                    continue
                yield ev
            await asyncio.gather(*tasks, return_exceptions=True)

        yield process_update_event("supervisor_root", "completed", "Multi-hop routing complete")


_supervisor_instance: Optional[SupervisorOrchestrator] = None


def get_supervisor_orchestrator() -> SupervisorOrchestrator:
    """Function: get_supervisor_orchestrator — provides a singleton supervisor orchestrator.
    Called from: conversational_analytics.routes.chat for agent_mode-aware requests.
    Invokes: get_conversational_analytics_agent to reuse the base agent instance.
    Purpose: Avoids repeated SDK/client construction and keeps routing state consistent."""
    global _supervisor_instance
    if _supervisor_instance is None:
        _supervisor_instance = SupervisorOrchestrator()
    return _supervisor_instance

