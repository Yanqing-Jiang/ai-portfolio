# --- A2UI Agent Function/Class Map ---
# Class: A2UIAgentError
#   Role: Typed exception for A2UI agent failures.
#   Called from: backend.generative_ui.routes.dashboard, backend.generative_ui.agent_v2
#   Invokes: n/a
#   Why: Standardizes error reporting for the A2UI pipeline.
# Dataclass: A2UIRunResult
#   Role: Bundle skill execution output + citations for persistence.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill, backend.generative_ui.routes.dashboard
#   Invokes: n/a
#   Why: Provides a consistent payload for streaming + storage.
# Dataclass: SkillExecutionChunk
#   Role: Stream incremental data patches and audit events during execution.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill_streaming,
#   backend.generative_ui.runtime.A2UIRuntime
#   Invokes: n/a
#   Why: Enables partial UI updates before full skill completion.
# Pydantic Model: SkillSelection
#   Role: Structured skill routing output for the model.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.select_skill, backend.generative_ui.agent_v2.A2UIAgent.selection_from_plan
#   Invokes: pydantic validation
#   Why: Enforces the selection contract used by skill routing.
# Class: A2UIAgent
#   Role: Orchestrate skill selection, tool execution, and A2UI streaming.      
#   Called from: backend.generative_ui.routes.dashboard
#   Invokes: Claude Agent SDK client, conversational_analytics.tools, backend.generative_ui.a2ui.emitter.A2UIMessageEmitter
#   Why: Implements the A2UI-native agent flow with SDK-backed selection and data streaming.
# Method: A2UIAgent.__init__
#   Role: Configure model + skill registry references.
#   Called from: backend.generative_ui.agent_v2.get_a2ui_agent
#   Invokes: backend.generative_ui.skills.get_a2ui_skills, A2UIAgent._build_selection_system_prompt
#   Why: Shares cached skill metadata across requests.
# Method: A2UIAgent.select_skill
#   Role: Use the Claude Agent SDK to select a skill and extract slots.
#   Called from: backend.generative_ui.routes.dashboard.create_dashboard        
#   Invokes: A2UIAgent._ensure_sdk_initialized, A2UISDKWrapper.query
#   Why: Keeps routing logic centralized and model-driven via the SDK.
# Method: A2UIAgent.selection_to_plan
#   Role: Convert a SkillSelection into a plan dict for storage.
#   Called from: backend.generative_ui.routes.dashboard.create_dashboard
#   Invokes: backend.generative_ui.skills.get_a2ui_skill
#   Why: Preserves routing outputs for downstream stream usage.
# Method: A2UIAgent.selection_from_plan
#   Role: Rehydrate a SkillSelection from stored plan JSON.
#   Called from: backend.generative_ui.routes.dashboard.stream_dashboard        
#   Invokes: cached skill lookup
#   Why: Avoids re-calling the model during streaming.
# Method: A2UIAgent._build_selection_system_prompt
#   Role: Build the stable system prompt used for SDK-backed skill routing.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.__init__
#   Invokes: n/a (uses prebuilt skill catalog)
#   Why: Separates cacheable routing context from per-request user prompts.
# Method: A2UIAgent._ensure_sdk_initialized
#   Role: Initialize the Claude Agent SDK with MCP tools and cacheable prompts.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.select_skill,
#   backend.generative_ui.agent_v2.A2UIAgent.execute_skill_streaming
#   Invokes: A2UISDKWrapper.initialize
#   Why: Ensures SDK + MCP tool configuration is ready for routing/streaming.
# Method: A2UIAgent.stream_dashboard
#   Role: Emit A2UI messages for a full dashboard session.
#   Called from: backend.generative_ui.routes.dashboard.stream_dashboard        
#   Invokes: backend.generative_ui.a2ui.emitter.A2UIMessageEmitter, A2UIAgent.execute_skill
#   Why: Provides the streaming backbone for the dashboard UI.
# Method: A2UIAgent.execute_skill
#   Role: Route tool execution based on the selected skill.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.stream_dashboard, backend.generative_ui.routes.dashboard.handle_action
#   Invokes: A2UIAgent._execute_explain_move/_execute_peer_compare/_execute_margin_analysis/_execute_revenue_trend, A2UIAgent._execute_narrative
#   Why: Keeps tool usage aligned with skill intent.
# Method: A2UIAgent.execute_skill_streaming
#   Role: Yield incremental data patches during skill execution.
#   Called from: backend.generative_ui.runtime.A2UIRuntime.stream_dashboard,
#   backend.generative_ui.runtime.A2UIRuntime.process_action
#   Invokes: A2UIAgent.execute_skill, A2UISDKWrapper.initialize
#   Why: Streams partial updates and ensures SDK tool wiring for runtime flows.
# Method: A2UIAgent._execute_narrative
#   Role: Generate concise narrative summaries for non-explain-move skills.     
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill
#   Invokes: conversational_analytics.tools.execute_analysis_tool
#   Why: Supplies summary copy for ExplainMovePanel on metric dashboards.       
# Method: A2UIAgent._execute_chart_annotations
#   Role: Build chart annotations from recent news events.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent._execute_margin_analysis, backend.generative_ui.agent_v2.A2UIAgent._execute_revenue_trend
#   Invokes: conversational_analytics.tools.execute_news_tool, backend.generative_ui.utils.date_to_period_label
#   Why: Aligns narrative events with chart periods.
# Method: A2UIAgent._execute_explain_move
#   Role: Run SQL + news tools and assemble explain-move data.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill
#   Invokes: conversational_analytics.tools.execute_sql_tool, conversational_analytics.tools.execute_news_tool, conversational_analytics.tools.execute_analysis_tool
#   Why: Supplies KPIs, news, and explanations for explain-move dashboards.
# Method: A2UIAgent._execute_peer_compare
#   Role: Run SQL tool and compute comparison, chart, and correlation outputs.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill
#   Invokes: conversational_analytics.tools.execute_sql_tool, backend.generative_ui.utils.compute_correlation_matrix
#   Why: Powers peer comparison dashboards with metric series.
# Method: A2UIAgent._execute_margin_analysis
#   Role: Run SQL tool and compute margin KPIs + chart series.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill
#   Invokes: conversational_analytics.tools.execute_sql_tool, A2UIAgent._execute_multi_ticker_margins
#   Why: Supplies margin analysis dashboards with data.
# Method: A2UIAgent._execute_multi_ticker_margins
#   Role: Build margin comparison data for multiple tickers.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent._execute_margin_analysis
#   Invokes: conversational_analytics.tools.execute_sql_tool
#   Why: Provides multi-ticker margin comparisons.
# Method: A2UIAgent._execute_revenue_trend
#   Role: Run SQL tool and compute revenue trend KPIs + chart series.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill
#   Invokes: conversational_analytics.tools.execute_sql_tool
#   Why: Supplies revenue trend dashboards with data.
# Method: A2UIAgent._validate_selection
#   Role: Validate skill selection inputs.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.select_skill, backend.generative_ui.agent_v2.A2UIAgent.stream_dashboard
#   Invokes: backend.generative_ui.utils.normalize_tickers
#   Why: Guards against unsupported tickers/time ranges.
# Method: A2UIAgent._build_render_context
#   Role: Build context used by layout emitters.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.stream_dashboard
#   Invokes: backend.generative_ui.agent_v2.A2UIAgent._build_title
#   Why: Keeps layout logic isolated from skill selection details.
# Method: A2UIAgent._build_title
#   Role: Generate dashboard titles based on skill + tickers.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent._build_render_context
#   Invokes: n/a
#   Why: Ensures consistent titles across dashboards.
# Function: get_a2ui_agent
#   Role: Provide a singleton A2UIAgent instance.
#   Called from: backend.generative_ui.routes.dashboard
#   Invokes: backend.generative_ui.agent_v2.A2UIAgent
#   Why: Avoids reloading skills and settings per request.
# --- End A2UI Agent Function/Class Map ---
"""
A2UI-native agent for skill-driven dashboard streaming.
"""

from __future__ import annotations

import json
import re
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from .config import get_settings
from .skills import A2UISkillMeta, build_a2ui_skill_catalog, get_a2ui_skill, get_a2ui_skills
from .a2ui.emitter import A2UIMessageEmitter, SkillRenderContext
from .sdk_wrapper import A2UISDKWrapper, get_sdk_wrapper, SDKResponse
from .mcp_tools import A2UI_MCP_TOOLS, A2UI_MCP_TOOL_NAMES
from .utils import (
    AVAILABLE_TICKERS,
    normalize_tickers,
    sorted_rows,
    period_label,
    coerce_float,
    metric_series,
    latest_and_previous,
    percentage_change,
    compute_correlation_matrix,
    parse_published_at,
    date_to_period_label,
    map_sentiment,
    map_news_event,
)
from conversational_analytics.tools import execute_sql_tool, execute_news_tool, execute_analysis_tool


logger = logging.getLogger(__name__)

ALLOWED_TIME_RANGES = {"1M", "3M", "6M", "1Y"}
DEFAULT_TIME_RANGE = "3M"
DEFAULT_METRIC = "Revenue"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class A2UIAgentError(Exception):
    """Raised when the A2UI agent fails."""


def extract_json_from_response(content: str) -> Dict[str, Any]:
    """
    Extract JSON from Claude's response, handling various formats.
    
    Function: extract_json_from_response
    Role: Parse JSON from model output that may include prose or code fences.
    Called from: A2UIAgent.select_skill
    Why: Claude may return JSON wrapped in prose or markdown code blocks.
    
    Args:
        content: Raw response text from Claude
        
    Returns:
        Parsed JSON dict
        
    Raises:
        ValueError: If no valid JSON found
    """
    if not content or not content.strip():
        raise ValueError("Empty response from model")
    
    content = content.strip()
    
    # Try direct JSON parse first (most efficient case)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from code blocks (```json ... ``` or ``` ... ```)
    code_block_pattern = r'```(?:json)?\s*([\s\S]*?)```'
    match = re.search(code_block_pattern, content)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON object anywhere in the response
    # Look for { ... } pattern
    json_pattern = r'\{[\s\S]*?\}'
    matches = re.findall(json_pattern, content)
    for m in matches:
        try:
            parsed = json.loads(m)
            # Verify it has expected keys
            if "skill_id" in parsed or "tickers" in parsed:
                return parsed
        except json.JSONDecodeError:
            continue
    
    # Last resort: try cleaning up common issues
    # Remove leading/trailing text before/after JSON
    content_cleaned = content
    if '{' in content_cleaned:
        start = content_cleaned.find('{')
        end = content_cleaned.rfind('}') + 1
        if start < end:
            try:
                return json.loads(content_cleaned[start:end])
            except json.JSONDecodeError:
                pass
    
    raise ValueError(f"Could not parse JSON from response: {content[:200]}...")


@dataclass(frozen=True)
class A2UIRunResult:
    """Container for skill execution results."""

    data_model: Dict[str, Any]
    citations: List[Dict[str, Any]]


@dataclass
class SkillExecutionChunk:
    """
    Chunk emitted during streaming skill execution.
    
    Dataclass: SkillExecutionChunk — holds incremental data for streaming.
    Called from: A2UIAgent.execute_skill_streaming
    Purpose: Enables the runtime to yield partial results (data patches, audit events)
    before the full skill execution completes.
    """
    step: str  # e.g., "sql_query", "news_fetch", "narrative", "complete"
    data_patch: Optional[Dict[str, Any]] = None
    data_path: Optional[str] = None  # JSON path like "/data/kpis" or "/data/chart"
    audit_event: Optional[str] = None
    audit_details: Optional[str] = None
    final_result: Optional[A2UIRunResult] = None


class SkillSelection(BaseModel):
    """Structured output for skill routing."""

    skill_id: str = Field(..., description="Selected skill_id from the catalog")
    tickers: List[str] = Field(default_factory=list, description="Ticker symbols referenced by the user")
    metric: str = Field(default=DEFAULT_METRIC, description="Primary metric for comparison")
    time_range: str = Field(default=DEFAULT_TIME_RANGE, description="Requested time range for charts")

    # JSON Schema examples for better Claude invocation (Optimization #10)
    model_config = {
        "json_schema_extra": {
            "examples": [
                {"skill_id": "explain_move", "tickers": ["NVDA"], "metric": "Revenue", "time_range": "3M"},
                {"skill_id": "peer_compare", "tickers": ["NVDA", "AMD", "INTC"], "metric": "Gross Margin", "time_range": "1Y"}
            ]
        }
    }

    @classmethod
    def get_json_schema_prompt(cls) -> str:
        """Get a prompt snippet with the JSON schema for Claude."""
        return (
            "Return JSON with keys: skill_id, tickers, metric, time_range.\n"
            'Example: {"skill_id": "explain_move", "tickers": ["NVDA"], "metric": "Revenue", "time_range": "3M"}'
        )


class A2UIAgent:
    """A2UI-native agent that streams dashboard messages."""

    def __init__(self, model: Optional[str] = None) -> None:
        """Initialize the agent with model + skill catalog."""
        self.settings = get_settings()
        if not self.settings.claude_api_key:
            raise A2UIAgentError("Claude API key not configured")
        self.model = model or self.settings.claude_model or DEFAULT_MODEL
        self.skills = get_a2ui_skills()
        self.skill_catalog = build_a2ui_skill_catalog(self.skills)
        self.skill_lookup = {skill.skill_id: skill for skill in self.skills}
        self._selection_system_prompt = self._build_selection_system_prompt()
        self._selection_prompt_cache_key = hashlib.sha256(
            self._selection_system_prompt.encode("utf-8")
        ).hexdigest()
        self._selection_prompt_initialized = False
        self.sdk_wrapper: A2UISDKWrapper = get_sdk_wrapper(
            model=self.model,
            api_key=self.settings.claude_api_key,
        )

    def _build_selection_system_prompt(self) -> str:
        """
        Build the stable system prompt used for skill routing.

        Method: A2UIAgent._build_selection_system_prompt
        Called from: A2UIAgent.__init__
        Invokes: n/a (uses prebuilt skill catalog)
        Purpose: Keeps routing context cacheable and consistent across requests.
        """
        base_prompt = (
            "You route financial dashboard requests to predefined A2UI skills.\n"
            "Choose the best matching skill_id from the catalog and fill slots."
        )
        return "\n".join([base_prompt, self.skill_catalog])

    async def _ensure_sdk_initialized(self) -> None:
        """
        Initialize the Claude Agent SDK with MCP tools and cacheable prompts.

        Method: A2UIAgent._ensure_sdk_initialized
        Called from: A2UIAgent.select_skill, A2UIAgent.execute_skill_streaming
        Invokes: A2UISDKWrapper.initialize
        Purpose: Ensures SDK + MCP tool wiring is ready for routing/streaming.
        """
        if self._selection_prompt_initialized:
            logger.debug(
                "selection_prompt_cache=hit key=%s",
                self._selection_prompt_cache_key,
            )
        else:
            logger.debug(
                "selection_prompt_cache=miss key=%s",
                self._selection_prompt_cache_key,
            )
            self._selection_prompt_initialized = True

        allowed_tools = A2UI_MCP_TOOL_NAMES or None
        mcp_tools = A2UI_MCP_TOOLS or None
        await self.sdk_wrapper.initialize(
            system_prompt=self._selection_system_prompt,
            allowed_tools=allowed_tools,
            mcp_tools=mcp_tools,
            use_sdk=False,  # Use stable Anthropic API (SDK is experimental)
        )

    async def select_skill(self, question: str, max_retries: int = 2) -> SkillSelection:
        """Select a skill and slots using the model with retry logic.
        
        Args:
            question: User's question to route.
            max_retries: Number of retries on validation failure (default: 2).
            
        Returns:
            SkillSelection with skill_id, tickers, metric, and time_range.
            
        Raises:
            A2UIAgentError: If skill selection fails after all retries.
        """
        last_error: Optional[Exception] = None
        allowed_ranges = ", ".join(sorted(ALLOWED_TIME_RANGES))

        for attempt in range(max_retries):
            try:
                await self._ensure_sdk_initialized()

                user_prompt = (
                    f"Question: {question}\n"
                    f"Allowed tickers: {', '.join(AVAILABLE_TICKERS)}\n"
                    f"Allowed time_range values: {allowed_ranges}\n"
                    "Return JSON only with keys: skill_id, tickers, metric, time_range.\n"
                    "Tickers must be uppercase (min 1, max 6). Default metric is 'Revenue'.\n"
                    "No code fences or extra text."
                )

                response: SDKResponse = await self.sdk_wrapper.query(
                    prompt=user_prompt,
                    max_tokens=256,
                    temperature=0.3 if attempt else 0.7,
                )
                if response.error:
                    raise A2UIAgentError(response.error)
                # Extract JSON from the response (handles prose, code fences, etc.)
                parsed = extract_json_from_response(response.content or "")
                selection = SkillSelection(
                    skill_id=str(parsed.get("skill_id", "")).strip(),
                    tickers=normalize_tickers(parsed.get("tickers") or []),
                    metric=str(parsed.get("metric") or DEFAULT_METRIC),
                    time_range=str(parsed.get("time_range") or DEFAULT_TIME_RANGE),
                )
                self._validate_selection(selection)
                return selection

            except (ValueError, A2UIAgentError, Exception) as exc:
                last_error = exc
                if attempt < max_retries - 1:
                    import logging
                    logging.getLogger(__name__).warning(
                        f"Skill selection attempt {attempt + 1} failed: {exc}. Retrying..."
                    )
                continue

        raise A2UIAgentError(
            f"Skill selection failed after {max_retries} attempts: {last_error}"
        )

    def selection_to_plan(self, selection: SkillSelection) -> Dict[str, Any]:
        """Convert a skill selection into plan JSON for storage."""
        skill = get_a2ui_skill(selection.skill_id)
        tickers = normalize_tickers(selection.tickers)
        if not tickers:
            raise A2UIAgentError("No valid tickers selected")
        primary = tickers[0]
        peers = tickers[1:]
        return {
            "skill_id": selection.skill_id,
            "skill_name": skill.name,
            "layout": skill.layout,
            "widgets": skill.widgets,
            "ticker": primary,
            "peers": peers,
            "tickers": tickers,
            "metric": selection.metric,
            "time_range": selection.time_range,
        }

    def selection_from_plan(self, plan: Mapping[str, Any]) -> SkillSelection:
        """Rehydrate a SkillSelection from stored plan JSON."""
        skill_id = str(plan.get("skill_id", "")).strip()
        if not skill_id:
            raise A2UIAgentError("Plan missing skill_id")
        if skill_id not in self.skill_lookup:
            raise A2UIAgentError(f"Unknown skill_id in plan: {skill_id}")
        tickers = plan.get("tickers") or []
        if not tickers:
            ticker = plan.get("ticker")
            peers = plan.get("peers") or []
            tickers = [t for t in [ticker, *peers] if t]
        normalized = normalize_tickers(tickers)
        if not normalized:
            raise A2UIAgentError("Plan did not contain valid tickers")
        metric = str(plan.get("metric") or DEFAULT_METRIC)
        time_range = str(plan.get("time_range") or DEFAULT_TIME_RANGE)
        return SkillSelection(
            skill_id=skill_id,
            tickers=normalized,
            metric=metric,
            time_range=time_range,
        )

    async def stream_dashboard(
        self,
        question: str,
        surface_id: str,
        *,
        plan: Optional[Mapping[str, Any]] = None,
        on_result: Optional[Callable[[A2UIRunResult], None]] = None,
    ) -> "Iterable[str]":
        """Stream a full A2UI dashboard session as JSON strings."""
        emitter = A2UIMessageEmitter(surface_id=surface_id, catalog_id=self.settings.catalog_id)
        yield emitter.begin_rendering()

        try:
            selection = self.selection_from_plan(plan) if plan else await self.select_skill(question)
            self._validate_selection(selection)
            skill = self.skill_lookup[selection.skill_id]
            context = self._build_render_context(selection, skill)

            components = emitter.build_components_for_skill(skill, context)
            yield emitter.surface_update(components)

            seed_data = {
                "title": context.title,
                "ticker": context.primary_ticker,
                "primary_ticker": context.primary_ticker,
                "tickers": context.tickers,
                "time_range": context.time_range,
                "metric": context.metric,
            }
            yield emitter.data_update(seed_data)

            result = await self.execute_skill(skill, selection)
            yield emitter.data_update(result.data_model)

            if on_result is not None:
                on_result(result)

            yield json.dumps({"done": True})
        except Exception as exc:
            for msg in emitter.error_surface("agent_error", str(exc)):
                yield msg
            yield json.dumps({"done": True})

    async def execute_skill(self, skill: A2UISkillMeta, selection: SkillSelection) -> A2UIRunResult:
        """Execute tools for the selected skill."""
        if skill.skill_id == "a2ui_explain_move":
            result = await self._execute_explain_move(selection)
        elif skill.skill_id == "a2ui_peer_compare":
            result = await self._execute_peer_compare(selection)
        elif skill.skill_id == "a2ui_margin_analysis":
            result = await self._execute_margin_analysis(selection)
        elif skill.skill_id == "a2ui_revenue_trend":
            result = await self._execute_revenue_trend(selection)
        else:
            raise A2UIAgentError(f"Unsupported skill_id: {skill.skill_id}")
        
        # Add narrative summary for all skills except explain_move (which has its own)
        if skill.skill_id != "a2ui_explain_move":
            narrative = await self._execute_narrative(selection, result.data_model)
            result.data_model["explanation"] = narrative
            
        return result

    async def execute_skill_streaming(
        self, skill: A2UISkillMeta, selection: SkillSelection
    ) -> "AsyncGenerator[SkillExecutionChunk, None]":
        """
        Execute a skill and yield incremental streaming chunks.
        
        Method: A2UIAgent.execute_skill_streaming — streaming wrapper for execute_skill.
        Called from: runtime.py (A2UIRuntime.stream_dashboard, A2UIRuntime.process_action)
        Purpose: Enables the runtime to yield partial results (data patches, audit events)
        as skill execution progresses, providing real-time feedback to the UI.
        
        Yields:
            SkillExecutionChunk objects with incremental data patches and the final result.
        """
        from typing import AsyncGenerator  # Import here to avoid circular imports

        await self._ensure_sdk_initialized()

        # Emit start of skill execution
        yield SkillExecutionChunk(
            step="skill_start",
            audit_event="skill_execution_started",
            audit_details=f"Executing {skill.skill_id}",
        )
        
        try:
            # Execute the skill (this is the heavy lifting)
            result = await self.execute_skill(skill, selection)
            
            # Emit data patches for key sections of the result
            if result.data_model.get("kpis"):
                yield SkillExecutionChunk(
                    step="kpis",
                    data_patch=result.data_model["kpis"],
                    data_path="/data/kpis",
                    audit_event="data_loaded",
                    audit_details="KPIs loaded",
                )

            if result.data_model.get("chart"):
                yield SkillExecutionChunk(
                    step="chart",
                    data_patch=result.data_model["chart"],
                    data_path="/data/chart",
                    audit_event="data_loaded",
                    audit_details="Chart data loaded",
                )

            if result.data_model.get("table"):
                yield SkillExecutionChunk(
                    step="table",
                    data_patch=result.data_model["table"],
                    data_path="/data/table",
                    audit_event="data_loaded",
                    audit_details="Table data loaded",
                )

            if result.data_model.get("explanation"):
                yield SkillExecutionChunk(
                    step="narrative",
                    data_patch=result.data_model["explanation"],
                    data_path="/data/explanation",
                    audit_event="narrative_generated",
                    audit_details="AI narrative complete",
                )

            # Emit final complete chunk with the full result
            yield SkillExecutionChunk(
                step="complete",
                data_patch=result.data_model,
                data_path="/data",
                audit_event="skill_execution_complete",
                audit_details=f"{skill.skill_id} execution complete",
                final_result=result,
            )
            
        except Exception as exc:
            yield SkillExecutionChunk(
                step="error",
                audit_event="skill_execution_error",
                audit_details=str(exc),
            )
            raise

    async def _execute_narrative(self, selection: SkillSelection, data_model: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a concise AI narrative summarizing the data results with dynamic factors.
        
        Function: _execute_narrative
        Called from: A2UIAgent.execute_skill
        Invokes: execute_analysis_tool, _generate_factors_from_data
        Why: Provides intelligent, data-driven factors instead of generic placeholders.
        """
        primary_ticker = selection.tickers[0] if selection.tickers else "the company"
        all_tickers = ", ".join(selection.tickers) if selection.tickers else primary_ticker
        metric = selection.metric or "Revenue"
        
        # Build findings based on available data (works for all skills)
        findings = self._extract_findings(selection, data_model)
        
        # Generate dynamic factors from actual data
        factors = self._generate_factors_from_data(selection, data_model)
        
        # Determine trend direction
        trend = self._determine_trend(data_model)
        
        # Build data summary based on skill type
        if selection.skill_id == "a2ui_peer_compare":
            data_summary_text = f"Comparing {metric} for {all_tickers}. " + " ".join(findings[:2])
        elif selection.skill_id == "a2ui_margin_analysis":
            data_summary_text = f"Margin analysis for {primary_ticker}. " + " ".join(findings[:2])
        else:
            data_summary_text = f"{metric} analysis for {primary_ticker}. " + " ".join(findings[:2])
        
        try:
            analysis_result = await execute_analysis_tool(
                data_summary=data_summary_text,
                key_findings=findings,
                trend_direction=trend,
            )
            
            text = " ".join(findings) if findings else "Analysis pending."
            if analysis_result.get("success"):
                text = analysis_result.get("analysis", {}).get("summary", text)
            
            return {
                "title": f"Insight: {metric} for {primary_ticker}",
                "text": text,
                "factors": factors,  # NOW POPULATED WITH REAL DATA!
                "citations": [],
            }
        except Exception as e:
            logger.warning("Narrative generation failed: %s", e)
            return {
                "title": f"Insight: {metric} for {primary_ticker}",
                "text": " ".join(findings) if findings else "Data visualized below.",
                "factors": factors,  # Still use generated factors even on AI failure
                "citations": [],
            }

    def _extract_findings(self, selection: SkillSelection, data_model: Dict[str, Any]) -> List[str]:
        """
        Extract key findings from the data model.
        
        Function: _extract_findings
        Called from: _execute_narrative
        Why: Builds structured findings for AI summarization.
        """
        findings = []
        metric = selection.metric or "Revenue"
        
        # Extract KPI findings
        kpis = data_model.get("kpis", {})
        for k, v in kpis.items():
            if v is not None and v != 0:
                label = k.replace('_', ' ').title()
                if "margin" in k.lower():
                    findings.append(f"{label}: {v:.1f}%")
                elif isinstance(v, (int, float)) and v >= 1e6:
                    findings.append(f"{label}: ${v/1e9:.2f}B" if v >= 1e9 else f"{label}: ${v/1e6:.1f}M")
                elif isinstance(v, float):
                    findings.append(f"{label}: {v:.2f}")
                else:
                    findings.append(f"{label}: {v}")
        
        # Extract table data findings
        table_rows = data_model.get("table", {}).get("rows", [])
        for row in table_rows[:3]:
            ticker = row.get("ticker", "")
            latest_value = row.get("latest_value")
            yoy_change = row.get("yoy_change")
            
            if ticker and latest_value is not None:
                if latest_value >= 1e9:
                    value_str = f"${latest_value/1e9:.2f}B"
                elif latest_value >= 1e6:
                    value_str = f"${latest_value/1e6:.1f}M"
                else:
                    value_str = f"{latest_value:.2f}%"
                
                finding = f"{ticker}: Latest {metric} of {value_str}"
                if yoy_change is not None:
                    direction = "up" if yoy_change > 0 else "down" if yoy_change < 0 else "flat"
                    finding += f" ({direction} {abs(yoy_change):.1f}% YoY)"
                findings.append(finding)
        
        # Extract correlation findings
        correlation = data_model.get("correlation", {})
        if correlation.get("matrix") and len(correlation.get("tickers", [])) > 1:
            matrix = correlation["matrix"]
            tickers_list = correlation["tickers"]
            if len(tickers_list) >= 2 and len(matrix) >= 2 and len(matrix[0]) > 1:
                corr_val = matrix[0][1]
                findings.append(f"Correlation between {tickers_list[0]} and {tickers_list[1]}: {corr_val:.2f}")
        
        return findings or [f"Analyzed {metric} data."]

    def _generate_factors_from_data(
        self, 
        selection: SkillSelection, 
        data_model: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate factor cards based on actual data, not generic placeholders.
        
        Function: _generate_factors_from_data
        Called from: _execute_narrative
        Why: Provides meaningful, data-driven insight factors for the UI.
        
        Returns list of factors like:
        [{"title": "AMD Performance", "description": "...", "impact": "positive", "icon": "📊"}, ...]
        """
        factors = []
        primary_ticker = selection.tickers[0] if selection.tickers else "N/A"
        metric = selection.metric or "Revenue"
        
        table_rows = data_model.get("table", {}).get("rows", [])
        kpis = data_model.get("kpis", {})
        
        # Factor 1: Primary ticker performance
        primary_row = next((r for r in table_rows if r.get("ticker") == primary_ticker), None)
        if primary_row:
            yoy = primary_row.get("yoy_change")
            latest = primary_row.get("latest_value", 0)
            
            if latest and latest != 0:
                if latest >= 1e9:
                    formatted = f"${latest/1e9:.2f}B"
                elif latest >= 1e6:
                    formatted = f"${latest/1e6:.2f}M"
                else:
                    formatted = f"{latest:.1f}%"
                
                yoy_str = f" ({yoy:+.1f}% YoY)" if yoy is not None else ""
                factors.append({
                    "title": f"{primary_ticker} {metric}",
                    "description": f"Latest {metric}: {formatted}{yoy_str}",
                    "impact": "positive" if (yoy or 0) > 0 else "negative" if (yoy or 0) < 0 else "neutral",
                    "source": "Financial Data",
                    "icon": "📊",
                })
        
        # Factor 2: Market leader insight (for multi-ticker comparisons)
        if len(table_rows) >= 2:
            sorted_rows = sorted(
                [r for r in table_rows if r.get("latest_value")], 
                key=lambda r: r.get("latest_value", 0) or 0, 
                reverse=True
            )
            if sorted_rows:
                leader = sorted_rows[0]
                if leader.get("ticker") != primary_ticker:
                    factors.append({
                        "title": "Market Leader",
                        "description": f"{leader.get('ticker')} leads the peer group in {metric}.",
                        "impact": "neutral",
                        "source": "Peer Analysis",
                        "icon": "🏆",
                    })
                elif len(sorted_rows) > 1:
                    # Primary ticker IS the leader
                    factors.append({
                        "title": "Market Leader",
                        "description": f"{primary_ticker} leads the peer group in {metric}.",
                        "impact": "positive",
                        "source": "Peer Analysis",
                        "icon": "🏆",
                    })
        
        # Factor 3: Margin-specific insights
        gm = kpis.get("gross_margin", 0)
        om = kpis.get("operating_margin", 0)
        nm = kpis.get("net_margin", 0)
        
        if gm or om or nm:
            if gm and gm != 0:
                factors.append({
                    "title": "Gross Margin",
                    "description": f"{primary_ticker} gross margin of {gm:.1f}% indicates cost efficiency.",
                    "impact": "positive" if gm > 40 else "neutral" if gm > 20 else "negative",
                    "source": "Profitability Analysis",
                    "icon": "💰",
                })
            elif nm and nm != 0:
                factors.append({
                    "title": "Net Profitability",
                    "description": f"Net margin of {nm:.1f}% shows bottom-line profitability.",
                    "impact": "positive" if nm > 10 else "neutral" if nm > 0 else "negative",
                    "source": "Profitability Analysis",
                    "icon": "📈",
                })
        
        # Factor 4: YoY trend
        if primary_row and primary_row.get("yoy_change") is not None:
            yoy = primary_row["yoy_change"]
            factors.append({
                "title": "Year-over-Year Trend",
                "description": f"{primary_ticker} {metric} {'grew' if yoy > 0 else 'declined'} {abs(yoy):.1f}% compared to last year.",
                "impact": "positive" if yoy > 5 else "negative" if yoy < -5 else "neutral",
                "source": "Historical Analysis",
                "icon": "📈" if yoy > 0 else "📉",
            })
        
        # Ensure at least 2-3 factors
        if len(factors) < 2:
            factors.append({
                "title": "Data Analysis",
                "description": f"Comprehensive {metric} analysis based on latest available data.",
                "impact": "neutral",
                "source": "Financial Data",
                "icon": "✅",
            })
        
        return factors[:4]  # Limit to 4 factors for clean UI

    def _determine_trend(self, data_model: Dict[str, Any]) -> str:
        """
        Analyze overall trend from data.
        
        Function: _determine_trend
        Called from: _execute_narrative
        Why: Provides trend context for AI summarization.
        """
        table_rows = data_model.get("table", {}).get("rows", [])
        if not table_rows:
            return "stable"
        
        positive = sum(1 for r in table_rows if (r.get("yoy_change") or 0) > 0)
        negative = sum(1 for r in table_rows if (r.get("yoy_change") or 0) < 0)
        
        if positive > negative:
            return "upward"
        elif negative > positive:
            return "downward"
        return "mixed"

    async def _execute_chart_annotations(self, tickers: List[str], period_set: set[str]) -> List[Dict[str, Any]]:
        """Fetch news and map to chart annotations if they land on valid chart periods."""
        annotations = []
        for ticker in tickers[:2]: # Limit to first 2 tickers to keep it snappy
            try:
                news = await execute_news_tool(ticker=ticker, limit=10)
                if news.get("success"):
                    for article in news.get("articles", []):
                        pub_date = article.get("published_at")
                        if not pub_date: continue
                        
                        period = date_to_period_label(str(pub_date))
                        if period in period_set:
                            annotations.append({
                                "period": period,
                                "ticker": ticker,
                                "label": "News",
                                "details": article.get("title", "Market update")
                            })
                            # Only one annotation per period per ticker to avoid clutter
                            period_set.remove(period)
            except Exception:
                continue
        return annotations

    async def _execute_explain_move(self, selection: SkillSelection) -> A2UIRunResult:
        """Fetch KPI + news data for explain-move dashboards."""
        ticker = normalize_tickers(selection.tickers)[0]
        sql = (
            "SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value "
            "FROM comp_financials "
            f"WHERE ticker = '{ticker}' AND metric IN ('Revenue', 'Net Income', 'Gross Margin') "
            "ORDER BY calendar_year DESC, calendar_quarter_num DESC "
            "LIMIT 24"
        )
        sql_result = await execute_sql_tool(sql, reason="Explain price movement KPIs")
        if not sql_result.get("success"):
            raise A2UIAgentError(sql_result.get("error", "SQL query failed"))

        rows = sorted_rows(sql_result.get("rows", []))
        revenue_series = metric_series(rows, "Revenue")
        net_income_series = metric_series(rows, "Net Income")
        gross_margin_series = metric_series(rows, "Gross Margin")

        revenue_latest, revenue_prev = latest_and_previous(revenue_series)
        net_latest, net_prev = latest_and_previous(net_income_series)
        gross_latest, _ = latest_and_previous(gross_margin_series)

        revenue_delta = percentage_change(revenue_latest, revenue_prev)
        net_delta = percentage_change(net_latest, net_prev)

        news_result = await execute_news_tool(ticker=ticker, limit=5)
        if not news_result.get("success"):
            raise A2UIAgentError(news_result.get("error", "News tool failed"))

        articles = news_result.get("articles", [])
        events = [map_news_event(article) for article in articles]
        factors = [
            {
                "title": article.get("title", ""),
                "description": article.get("summary", ""),
                "impact": map_sentiment(coerce_float(article.get("sentiment_score")), article.get("sentiment_label")),
                "source": article.get("source", ""),
            }
            for article in articles[:3]
        ]
        citations = [
            {
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "date": parse_published_at(str(article.get("published_at") or "")),
            }
            for article in articles
        ]

        findings = []
        if revenue_delta is not None:
            findings.append(f"Revenue changed {revenue_delta:.2f}% quarter-over-quarter.")
        if net_delta is not None:
            findings.append(f"Net income changed {net_delta:.2f}% quarter-over-quarter.")
        if articles:
            findings.append(f"News sentiment leans {news_result.get('aggregate_label', 'Neutral')}.")

        analysis_result = await execute_analysis_tool(
            data_summary=f"Summary of recent metrics and news for {ticker}.",
            key_findings=findings or ["Recent financial metrics were reviewed."],
            trend_direction="mixed",
        )
        analysis_text = ""
        if analysis_result.get("success"):
            analysis = analysis_result.get("analysis", {})
            analysis_text = analysis.get("summary", "")

        data_model = {
            "ticker": ticker,
            "kpis": {
                "revenue": revenue_latest or 0,
                "revenue_delta": revenue_delta or 0,
                "net_income": net_latest or 0,
                "net_income_delta": net_delta or 0,
                "gross_margin": gross_latest or 0,
            },
            "news": {"events": events},
            "explanation": {
                "title": f"{ticker} Movement Drivers",
                "text": analysis_text or "Analysis pending.",
                "factors": factors,
                "citations": citations,
            },
        }
        return A2UIRunResult(data_model=data_model, citations=citations)

    async def _execute_peer_compare(self, selection: SkillSelection) -> A2UIRunResult:
        """Fetch comparison data for peer dashboards."""
        tickers = normalize_tickers(selection.tickers)
        if len(tickers) < 2:
            raise A2UIAgentError("Peer comparison requires at least two tickers")
        tickers_sql = ", ".join([f"'{t}'" for t in tickers])
        metric = selection.metric or DEFAULT_METRIC
        sql = (
            "SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value "
            "FROM comp_financials "
            f"WHERE ticker IN ({tickers_sql}) AND metric = '{metric}' "
            "ORDER BY ticker, calendar_year DESC, calendar_quarter_num DESC "
            "LIMIT 200"
        )
        sql_result = await execute_sql_tool(sql, reason="Peer comparison metrics")
        if not sql_result.get("success"):
            raise A2UIAgentError(sql_result.get("error", "SQL query failed"))

        rows = sorted_rows(sql_result.get("rows", []))
        rows_by_ticker: Dict[str, List[Mapping[str, Any]]] = {ticker: [] for ticker in tickers}
        for row in rows:
            ticker = row.get("ticker")
            if ticker in rows_by_ticker:
                rows_by_ticker[ticker].append(row)

        table_rows = []
        chart_series: List[Dict[str, Any]] = []
        series_by_ticker: Dict[str, List[float]] = {}
        for ticker, ticker_rows in rows_by_ticker.items():
            series = metric_series(ticker_rows, metric)
            latest, _previous = latest_and_previous(series)
            yoy_change = None
            if len(series) > 4:
                yoy_value = coerce_float(series[4].get("value"))
                yoy_change = percentage_change(latest, yoy_value)
            series_values = [entry["value"] for entry in series]
            series_by_ticker[ticker] = series_values
            chart_series.append({"ticker": ticker, "data": series})
            table_rows.append(
                {
                    "ticker": ticker,
                    "latest_value": latest if latest is not None else 0,
                    "yoy_change": yoy_change,
                }
            )

        metric_lower = metric.lower()
        value_type = "percentage" if "margin" in metric_lower or "rate" in metric_lower else "currency"
        columns = [
            {"key": "ticker", "label": "Ticker", "type": "string"},
            {"key": "latest_value", "label": f"Latest {metric}", "type": value_type},
            {"key": "yoy_change", "label": "YoY %", "type": "percentage"},
        ]

        correlation = compute_correlation_matrix(series_by_ticker, tickers)

        data_model = {
            "tickers": tickers,
            "primary_ticker": tickers[0],
            "table": {"columns": columns, "rows": table_rows},
            "correlation": {"tickers": tickers, "matrix": correlation},
            "chart": {"series": chart_series, "annotations": []},
        }
        return A2UIRunResult(data_model=data_model, citations=[])

    async def _execute_margin_analysis(self, selection: SkillSelection) -> A2UIRunResult:
        """Fetch margin KPIs and history. Supports single or multi-ticker margin comparisons."""
        tickers = normalize_tickers(selection.tickers)
        if not tickers:
            raise A2UIAgentError("No valid tickers for margin analysis")

        # Multi-ticker margin comparison
        if len(tickers) > 1:
            return await self._execute_multi_ticker_margins(tickers)

        # Single ticker margin analysis - fetch all possible margin metrics
        ticker = tickers[0]
        sql = (
            "SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value "
            "FROM comp_financials "
            f"WHERE ticker = '{ticker}' AND metric IN "
            "('Gross Margin', 'Operating Margin', 'Net Income', 'Revenue', "
            "'Gross Profit', 'Operating Income', 'Cost of Revenue') "
            "ORDER BY calendar_year DESC, calendar_quarter_num DESC "
            "LIMIT 80"
        )
        sql_result = await execute_sql_tool(sql, reason="Margin analysis")
        if not sql_result.get("success"):
            raise A2UIAgentError(sql_result.get("error", "SQL query failed"))

        rows = sorted_rows(sql_result.get("rows", []))
        
        # Try direct margin values first, then calculate from components
        gross_series = metric_series(rows, "Gross Margin")
        operating_series = metric_series(rows, "Operating Margin")
        revenue_series = metric_series(rows, "Revenue")
        net_income_series = metric_series(rows, "Net Income")
        gross_profit_series = metric_series(rows, "Gross Profit")
        operating_income_series = metric_series(rows, "Operating Income")
        cost_of_revenue_series = metric_series(rows, "Cost of Revenue")
        
        # Build period-based lookup for calculations
        revenue_by_period = {entry["period"]: entry["value"] for entry in revenue_series}
        net_income_by_period = {entry["period"]: entry["value"] for entry in net_income_series}
        gross_profit_by_period = {entry["period"]: entry["value"] for entry in gross_profit_series}
        operating_income_by_period = {entry["period"]: entry["value"] for entry in operating_income_series}
        cost_of_revenue_by_period = {entry["period"]: entry["value"] for entry in cost_of_revenue_series}
        
        # Calculate Gross Margin if not directly available
        if not gross_series:
            for entry in revenue_series:
                period = entry["period"]
                revenue = entry["value"]
                if revenue == 0:
                    continue
                gross_profit = gross_profit_by_period.get(period)
                cost = cost_of_revenue_by_period.get(period)
                if gross_profit is not None:
                    gross_series.append({"period": period, "value": (gross_profit / revenue) * 100})
                elif cost is not None:
                    gross_series.append({"period": period, "value": ((revenue - cost) / revenue) * 100})
        
        # Calculate Operating Margin if not directly available
        if not operating_series:
            for entry in revenue_series:
                period = entry["period"]
                revenue = entry["value"]
                op_income = operating_income_by_period.get(period)
                if op_income is not None and revenue != 0:
                    operating_series.append({"period": period, "value": (op_income / revenue) * 100})
        
        gross_latest, _ = latest_and_previous(gross_series)
        operating_latest, _ = latest_and_previous(operating_series)

        # Calculate Net Margin from Net Income / Revenue
        net_margin_series: List[Dict[str, Any]] = []
        for entry in revenue_series:
            period = entry["period"]
            revenue_value = entry["value"]
            net_value = net_income_by_period.get(period)
            if net_value is None or revenue_value == 0:
                continue
            net_margin_series.append({"period": period, "value": (net_value / revenue_value) * 100})

        net_latest, _ = latest_and_previous(net_margin_series)

        table_rows = []
        for entry in revenue_series[:8]:
            period = entry["period"]
            table_rows.append(
                {
                    "period": period,
                    "gross_margin": next((item["value"] for item in gross_series if item["period"] == period), None),
                    "operating_margin": next((item["value"] for item in operating_series if item["period"] == period), None),
                    "net_margin": next((item["value"] for item in net_margin_series if item["period"] == period), None),
                }
            )

        columns = [
            {"key": "period", "label": "Period", "type": "string"},
            {"key": "gross_margin", "label": "Gross Margin", "type": "percentage"},
            {"key": "operating_margin", "label": "Operating Margin", "type": "percentage"},
            {"key": "net_margin", "label": "Net Margin", "type": "percentage"},
        ]

        chart_series = [
            {"ticker": "Gross Margin", "data": gross_series},
            {"ticker": "Operating Margin", "data": operating_series},
            {"ticker": "Net Margin", "data": net_margin_series},
        ]

        data_model = {
            "ticker": ticker,
            "kpis": {
                "gross_margin": gross_latest or 0,
                "operating_margin": operating_latest or 0,
                "net_margin": net_latest or 0,
            },
            "table": {"columns": columns, "rows": table_rows},
            "chart": {
                "series": chart_series,
                "annotations": [],
            },
        }

        # Add annotations to chart
        periods = {entry["period"] for entry in revenue_series}
        data_model["chart"]["annotations"] = await self._execute_chart_annotations([ticker], periods)
        
        return A2UIRunResult(data_model=data_model, citations=[])

    async def _execute_multi_ticker_margins(self, tickers: List[str]) -> A2UIRunResult:
        """Fetch margin comparison data for multiple tickers with fallback calculations."""
        tickers_sql = ", ".join([f"'{t}'" for t in tickers])
        sql = (
            "SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value "
            "FROM comp_financials "
            f"WHERE ticker IN ({tickers_sql}) AND metric IN "
            "('Gross Margin', 'Operating Margin', 'Net Income', 'Revenue', "
            "'Gross Profit', 'Operating Income', 'Cost of Revenue') "
            "ORDER BY ticker, calendar_year DESC, calendar_quarter_num DESC "
            "LIMIT 400"
        )
        sql_result = await execute_sql_tool(sql, reason="Multi-ticker margin comparison")
        if not sql_result.get("success"):
            raise A2UIAgentError(sql_result.get("error", "SQL query failed"))

        rows = sorted_rows(sql_result.get("rows", []))
        rows_by_ticker: Dict[str, List[Mapping[str, Any]]] = {ticker: [] for ticker in tickers}
        for row in rows:
            ticker = row.get("ticker")
            if ticker in rows_by_ticker:
                rows_by_ticker[ticker].append(row)

        table_rows = []
        chart_series: List[Dict[str, Any]] = []
        for ticker, ticker_rows in rows_by_ticker.items():
            # Get direct margin values first
            gross_series = metric_series(ticker_rows, "Gross Margin")
            operating_series = metric_series(ticker_rows, "Operating Margin")
            revenue_series = metric_series(ticker_rows, "Revenue")
            net_income_series = metric_series(ticker_rows, "Net Income")
            gross_profit_series = metric_series(ticker_rows, "Gross Profit")
            operating_income_series = metric_series(ticker_rows, "Operating Income")
            cost_of_revenue_series = metric_series(ticker_rows, "Cost of Revenue")
            
            # Build period lookups
            revenue_by_period = {e["period"]: e["value"] for e in revenue_series}
            net_income_by_period = {e["period"]: e["value"] for e in net_income_series}
            gross_profit_by_period = {e["period"]: e["value"] for e in gross_profit_series}
            operating_income_by_period = {e["period"]: e["value"] for e in operating_income_series}
            cost_by_period = {e["period"]: e["value"] for e in cost_of_revenue_series}
            
            # Calculate Gross Margin if not directly available
            if not gross_series:
                for entry in revenue_series:
                    period = entry["period"]
                    revenue = entry["value"]
                    if revenue == 0:
                        continue
                    gp = gross_profit_by_period.get(period)
                    cost = cost_by_period.get(period)
                    if gp is not None:
                        gross_series.append({"period": period, "value": (gp / revenue) * 100})
                    elif cost is not None:
                        gross_series.append({"period": period, "value": ((revenue - cost) / revenue) * 100})
            
            # Calculate Operating Margin if not directly available
            if not operating_series:
                for entry in revenue_series:
                    period = entry["period"]
                    revenue = entry["value"]
                    op_income = operating_income_by_period.get(period)
                    if op_income is not None and revenue != 0:
                        operating_series.append({"period": period, "value": (op_income / revenue) * 100})

            gross_latest, _ = latest_and_previous(gross_series)
            operating_latest, _ = latest_and_previous(operating_series)

            # Calculate Net Margin from Net Income / Revenue
            net_margin_series: List[Dict[str, Any]] = []
            for entry in revenue_series:
                period = entry["period"]
                revenue_value = entry["value"]
                net_value = net_income_by_period.get(period)
                if net_value is None or revenue_value == 0:
                    continue
                net_margin_series.append({"period": period, "value": (net_value / revenue_value) * 100})
            net_margin = net_margin_series[0]["value"] if net_margin_series else None
            if net_margin_series:
                chart_series.append({"ticker": ticker, "data": net_margin_series})

            table_rows.append({
                "ticker": ticker,
                "gross_margin": gross_latest or 0,
                "operating_margin": operating_latest or 0,
                "net_margin": net_margin or 0,
            })

        columns = [
            {"key": "ticker", "label": "Ticker", "type": "string"},
            {"key": "gross_margin", "label": "Gross Margin", "type": "percentage"},
            {"key": "operating_margin", "label": "Operating Margin", "type": "percentage"},
            {"key": "net_margin", "label": "Net Margin", "type": "percentage"},
        ]

        data_model = {
            "tickers": tickers,
            "primary_ticker": tickers[0],
            "kpis": {
                "gross_margin": table_rows[0]["gross_margin"] if table_rows else 0,
                "operating_margin": table_rows[0]["operating_margin"] if table_rows else 0,
                "net_margin": table_rows[0]["net_margin"] if table_rows else 0,
            },
            "table": {"columns": columns, "rows": table_rows},
            "chart": {"series": chart_series, "annotations": []},
        }
        return A2UIRunResult(data_model=data_model, citations=[])

    async def _execute_revenue_trend(self, selection: SkillSelection) -> A2UIRunResult:
        """Fetch revenue trend metrics."""
        ticker = normalize_tickers(selection.tickers)[0]
        sql = (
            "SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value "
            "FROM comp_financials "
            f"WHERE ticker = '{ticker}' AND metric = 'Revenue' "
            "ORDER BY calendar_year DESC, calendar_quarter_num DESC "
            "LIMIT 24"
        )
        sql_result = await execute_sql_tool(sql, reason="Revenue trend")
        if not sql_result.get("success"):
            raise A2UIAgentError(sql_result.get("error", "SQL query failed"))

        rows = sorted_rows(sql_result.get("rows", []))
        revenue_series = metric_series(rows, "Revenue")
        latest, previous = latest_and_previous(revenue_series)

        yoy_growth = None
        if len(revenue_series) > 4:
            yoy_value = revenue_series[4].get("value")
            yoy_growth = percentage_change(latest, coerce_float(yoy_value))

        columns = [
            {"key": "period", "label": "Period", "type": "string"},
            {"key": "revenue", "label": "Revenue", "type": "currency"},
        ]
        rows_table = [
            {"period": entry["period"], "revenue": entry["value"]}
            for entry in revenue_series[:8]
        ]

        chart_series = [{"ticker": ticker, "data": revenue_series}]

        data_model = {
            "ticker": ticker,
            "kpis": {
                "latest_revenue": latest or 0,
                "yoy_growth": yoy_growth or 0,
            },
            "table": {"columns": columns, "rows": rows_table},
            "chart": {
                "series": chart_series,
                "annotations": [],
            },
        }

        # Add annotations to chart
        periods = {entry["period"] for entry in revenue_series}
        data_model["chart"]["annotations"] = await self._execute_chart_annotations([ticker], periods)
        
        return A2UIRunResult(data_model=data_model, citations=[])

    def _validate_selection(self, selection: SkillSelection) -> None:
        if selection.skill_id not in self.skill_lookup:
            raise A2UIAgentError(f"Unknown skill_id: {selection.skill_id}")
        if selection.time_range not in ALLOWED_TIME_RANGES:
            raise A2UIAgentError(f"Invalid time_range: {selection.time_range}")
        normalized = normalize_tickers(selection.tickers)
        if not normalized:
            raise A2UIAgentError("No valid tickers provided")
        selection.tickers = normalized

    def _build_render_context(self, selection: SkillSelection, skill: A2UISkillMeta) -> SkillRenderContext:
        tickers = normalize_tickers(selection.tickers)
        primary = tickers[0] if tickers else ""
        title = self._build_title(skill, tickers, selection.metric)
        return SkillRenderContext(
            title=title,
            primary_ticker=primary,
            tickers=tickers,
            time_range=selection.time_range,
            metric=selection.metric or DEFAULT_METRIC,
        )

    def _build_title(self, skill: A2UISkillMeta, tickers: Sequence[str], metric: str) -> str:
        if skill.skill_id == "a2ui_peer_compare":
            return f"Comparing {', '.join(tickers)}"
        if skill.skill_id == "a2ui_margin_analysis":
            if len(tickers) > 1:
                return f"{' vs '.join(tickers)} Margin Comparison"
            return f"{tickers[0]} Margin Analysis" if tickers else "Margin Analysis"
        if skill.skill_id == "a2ui_revenue_trend":
            return f"{tickers[0]} Revenue Trend" if tickers else "Revenue Trend"
        return f"{tickers[0]} Price Movement" if tickers else "Price Movement Analysis"


_agent_instance: Optional[A2UIAgent] = None


def get_a2ui_agent() -> A2UIAgent:
    """Get or create the singleton A2UI agent."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = A2UIAgent()
    return _agent_instance
