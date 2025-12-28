"""Conversational Analytics Agent - Claude-powered single agent with tool use."""
from __future__ import annotations

import json
import logging
import time
import uuid as py_uuid
import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional

try:
    import anthropic  # type: ignore
    _anthropic_import_error: Optional[ImportError] = None
except ImportError as exc:  # pragma: no cover - optional dependency
    anthropic = None  # type: ignore
    _anthropic_import_error = exc

try:
    from anthropic import ClaudeSDKClient, ClaudeAgentOptions  # type: ignore
except Exception:  # pragma: no cover - SDK may be unavailable
    ClaudeSDKClient = None  # type: ignore
    ClaudeAgentOptions = None  # type: ignore

from .config import settings
from .memory import session_store
from .tools import ALL_TOOLS, TOOL_EXECUTORS, is_web_search_tool, format_web_search_results
from .skills import (
    get_skill_by_id,
    load_skill_instructions,
    build_skill_catalog,
    extract_skill_from_response,
    resolve_slots,
    SlotSpec,
    SKILL_INDEX,
)
from .sdk_assets import (
    get_allowed_tools,
    load_project_guide,
    load_project_settings,
    should_use_sdk_assets,
)
from .streaming import (
    status_event,
    thinking_event,
    tool_start_event,
    tool_end_event,
    content_event,
    chart_event,
    data_event,
    skill_event,
    news_event,
    plan_event,
    plan_update_event,
    done_event,
    error_event,
    html_artifact_event,
    debug_event,
    selection_request_event,
    process_node_event,
    process_edge_event,
    process_update_event,
    process_clear_event,
    set_run_context,
    set_step_context,
    clear_run_context,
)

logger = logging.getLogger(__name__)

# System prompt base (skill catalog is appended dynamically)
SYSTEM_PROMPT_BASE = """You are a conversational analytics assistant specialized in financial data analysis for semiconductor companies.

You have access to a database with financial metrics for these companies:
- NVDA (NVIDIA), AMD, INTC (Intel), AVGO (Broadcom), QCOM (Qualcomm), MU (Micron), TXN (Texas Instruments)

Available metrics include: Revenue, Net Income, Gross Margin, Operating Margin, EPS, Free Cash Flow, Total Assets, R&D Expenses, and more.

Your capabilities:
1. **query_database** - Query the comp_financials table for financial data
2. **generate_echarts** - Create interactive charts (bar, line, pie, area) from data
3. **create_tradingview_chart** - Display stock price charts
4. **generate_analysis** - Provide narrative insights
5. **web_search** - Search the web for current market news and context

Workflow:
1. When asked about financials, first use query_database to get the data
2. Then use generate_echarts to visualize if appropriate
3. Provide analysis and insights in your response
4. Use web_search for current news or real-time context

Multi-turn guidance:
- Always reuse prior query results when the user follows up (e.g., “focus on margins”, “compare to last quarter”, “rerun for AMD”). Avoid re-querying unless data is missing.
- Cite which earlier turn the reused data came from.
- When comparing tickers or periods, minimize redundant SQL by batching queries.
- Avoid deterministic scripted steps; choose tools dynamically based on the latest user intent.

Format numbers as: $1.2B (billions), $150M (millions), 15.3% (percentages)

Guardrails:
- Never include raw tool request/response JSON in the final answer; summarize results only.
- Do not paste tool inputs or outputs into the user-facing text.

Be conversational, accurate, and insightful. Always cite the data source when using web search."""


def _get_system_prompt_with_skills() -> str:
    """Function: _get_system_prompt_with_skills — builds complete system prompt with skill catalog.
    Called from: agent initialization and run_with_tools.
    Purpose: Combines base prompt with skill descriptions so Claude can decide which skill to use."""
    skill_catalog = build_skill_catalog()
    return f"{SYSTEM_PROMPT_BASE}\n\n{skill_catalog}"


# Full system prompt with skill catalog
SYSTEM_PROMPT = _get_system_prompt_with_skills()


class MissingDependencyError(RuntimeError):
    """Raised when required third-party dependencies are unavailable."""


def _build_hitl_options(ambiguous_slots: List[SlotSpec], max_options: int = 3) -> List[Dict[str, Any]]:
    """Function: _build_hitl_options — builds up to max_options bundled choices from ambiguous slots.
    Called from: run_with_tools when slot resolution finds ambiguous required slots.
    Purpose: Creates user-friendly option cards for HITL selection."""
    # local import removed; uses module-level py_uuid
    if not ambiguous_slots:
        return []
    
    # If only one ambiguous slot with defined options, use those directly
    if len(ambiguous_slots) == 1:
        slot = ambiguous_slots[0]
        options = []
        for opt_value in slot.options[:max_options]:
            label = opt_value.replace("_", " ").title()
            options.append({
                "id": f"{slot.name}_{opt_value}",
                "label": label,
                "description": f"Set {slot.name} to {opt_value}",
                "payload": {slot.name: opt_value},
            })
        return options
    
    # Multiple ambiguous slots: bundle common combinations
    # For simplicity, create options from first slot's options combined with defaults for others
    first_slot = ambiguous_slots[0]
    options = []
    
    for opt_value in first_slot.options[:max_options]:
        payload = {first_slot.name: opt_value}
        # Use defaults for other ambiguous slots
        for other_slot in ambiguous_slots[1:]:
            if other_slot.default is not None:
                payload[other_slot.name] = other_slot.default
            elif other_slot.options:
                payload[other_slot.name] = other_slot.options[0]
        
        label_parts = [f"{first_slot.name}: {opt_value}"]
        for other_slot in ambiguous_slots[1:]:
            if other_slot.name in payload:
                label_parts.append(f"{other_slot.name}: {payload[other_slot.name]}")
        
        options.append({
            "id": str(py_uuid.uuid4())[:8],
            "label": ", ".join(label_parts).replace("_", " ").title(),
            "description": f"Use these settings",
            "payload": payload,
        })
    
    return options


def _build_system_blocks(
    base_system_prompt: str,
    project_guide: Optional[str],
    skill_block: Optional[str],
    resolved_slots_block: Optional[str],
) -> List[Dict[str, Any]]:
    """Function: _build_system_blocks — called from ConversationalAnalyticsAgent.run_with_tools to compose Claude system blocks with cache breakpoints.
    Invokes: None (pure helper).
    Purpose: Separates stable base prompt (cached), project guide (cached), skill prompt (cached), and per-turn slot guidance (uncached) to enable prompt caching without losing dynamic context."""
    blocks: List[Dict[str, Any]] = [
        {
            "type": "text",
            "text": base_system_prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    if project_guide:
        blocks.append(
            {
                "type": "text",
                "text": project_guide,
                "cache_control": {"type": "ephemeral"},
            }
        )
    if skill_block:
        blocks.append(
            {
                "type": "text",
                "text": skill_block,
                "cache_control": {"type": "ephemeral"},
            }
        )
    if resolved_slots_block:
        blocks.append(
            {
                "type": "text",
                "text": resolved_slots_block,
            }
        )
    return blocks


class ConversationalAnalyticsAgent:
    """Single agent for conversational analytics with Claude."""
    
    def __init__(self):
        if anthropic is None or _anthropic_import_error:
            raise MissingDependencyError(
                "Conversational Analytics requires the 'anthropic' package. "
                "Install backend dependencies (pip install -r backend/requirements.txt)."
            ) from _anthropic_import_error
        self.use_sdk_assets = should_use_sdk_assets(settings.use_sdk_assets)
        self.sdk_settings = load_project_settings() if self.use_sdk_assets else {}
        self.project_guide = load_project_guide() if self.use_sdk_assets else None
        self.sdk_client = None
        self.allowed_tool_names = get_allowed_tools([tool["name"] for tool in ALL_TOOLS]) if self.use_sdk_assets else [tool["name"] for tool in ALL_TOOLS]
        timeouts = self.sdk_settings.get("timeouts", {}) if self.sdk_settings else {}
        self.run_deadline_seconds: Optional[int] = timeouts.get("run_seconds")
        self.default_tool_timeout: Optional[int] = timeouts.get("default_tool_seconds")
        self.per_tool_timeout: Dict[str, Any] = timeouts.get("per_tool", {})
        self.tool_failures: Dict[str, int] = {}
        self.max_tool_failures = 3
        if not self.use_sdk_assets:
            logger.info("SDK assets disabled or missing; using legacy prompt path.")

        # Prefer Claude Agent SDK client when available; fall back to standard Anthropics client.
        if self.use_sdk_assets and ClaudeSDKClient and ClaudeAgentOptions:
            try:
                self.sdk_client = ClaudeSDKClient(
                    api_key=settings.claude_api_key,
                    options=ClaudeAgentOptions(
                        setting_sources=["project"],
                        allowed_tools=self.allowed_tool_names,
                        project_path=str(settings.sdk_project_path),
                    ),
                )
                self.client = self.sdk_client
                logger.info("Claude Agent SDK client initialized with project settings.")
            except Exception as exc:  # pragma: no cover - safe fallback path
                logger.warning("Falling back to Anthropics client (SDK init failed): %s", exc)
                self.client = anthropic.Anthropic(api_key=settings.claude_api_key)
        else:
            self.client = anthropic.Anthropic(api_key=settings.claude_api_key)
        self.model = settings.claude_model
        
    async def run_with_tools(
        self,
        message: str,
        session_id: str,
        *,
        system_prompt_override: Optional[str] = None,
        tool_allowlist: Optional[List[str]] = None,
        plan_steps_override: Optional[List[Dict[str, Any]]] = None,
        agent_label: Optional[str] = None,
        agent_mode: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Function: run_with_tools — called from conversational_analytics.routes.chat stream_chat/chat endpoints to drive SSE responses.
        Invokes: session_store for history, Anthropic streaming, and TOOL_EXECUTORS to emit SSE events.
        Purpose: Orchestrates Claude + tool use for conversational analytics conversations and streams client-facing events.
        Supports: Optional prompt/tool/plan overrides for supervisor and specialist routing."""
        debug_mode = settings.debug_mode
        start_total = time.monotonic()
        run_id = str(py_uuid.uuid4())
        set_run_context(run_id)
        
        # Clear previous process visualization when running standalone; supervisor handles its own root nodes
        if not agent_mode:
            yield process_clear_event()
        yield process_node_event(
            node_id="request_received",
            node_type="input",
            label="Request Received",
            status="completed",
            description=f"User message: {message[:100]}{'...' if len(message) > 100 else ''}",
        )
        
        if debug_mode and agent_label:
            yield debug_event("agent", f"Agent mode: {agent_label}", {"agent_mode": agent_mode or agent_label})
        
        # Debug: Session initialization
        if debug_mode:
            yield debug_event("session", f"Getting/creating session: {session_id}")
        
        # Get or create session
        session = session_store.get_or_create(session_id)
        session_store.start_run_trace(session_id, run_id)
        session.update_context("last_run_id", run_id)
        if session.consume_cancel():
            yield error_event("Run cancelled", "cancelled")
            yield done_event()
            clear_run_context()
            return
        
        if debug_mode:
            yield debug_event("session", "Session ready", {
                "session_id": session_id,
                "history_count": len(session.messages),
            })
        
        # Add user message to history
        session.add_message("user", message)
        
        if debug_mode:
            yield debug_event("agent", f"User message received ({len(message)} chars)")

        # Claude-native skill routing: Claude decides which skill to use based on context
        # The system prompt includes skill catalog with descriptions
        yield process_node_event(
            node_id="skill_detection",
            node_type="decision",
            label="Skill Detection",
            status="running",
            parent_id="request_received",
            description="Claude will decide based on context",
        )
        yield process_edge_event("request_received", "skill_detection", animated=True)
        
        base_system_prompt = system_prompt_override or SYSTEM_PROMPT
        
        # Mark skill detection as ready (Claude will indicate skill in response)
        yield process_update_event(
            node_id="skill_detection",
            status="completed",
            summary="Claude-native routing",
        )
        
        if debug_mode:
            yield debug_event("agent", "Using Claude-native skill routing (no pre-selection)")

        project_guide_block = self.project_guide if (self.use_sdk_assets and system_prompt_override is None) else None
        system_blocks = _build_system_blocks(
            base_system_prompt=base_system_prompt,
            project_guide=project_guide_block,
            skill_block=None,  # Skills are now in the base system prompt
            resolved_slots_block=None,
        )
        
        yield status_event("Connecting to Claude...")
        plan_steps = plan_steps_override or [
            {"id": "understand", "label": "Understand question", "status": "running"},
            {"id": "sql", "label": "Query comp_financials", "status": "pending"},
            {"id": "visualize", "label": "Build chart", "status": "pending"},
            {"id": "analysis", "label": "Summarize insights", "status": "pending"},
        ]
        set_step_context("plan")
        yield plan_event(plan_steps)
        yield thinking_event("query_analysis", "running", "Analyzing your question...")
        
        # Emit Claude API node
        yield process_node_event(
            node_id="claude_api",
            node_type="agent",
            label="Claude Analysis",
            status="running",
            parent_id="skill_detection",
            description="Connecting to Claude for analysis",
        )
        yield process_edge_event(
            "skill_detection",
            "claude_api",
            animated=True,
        )
        
        try:
            # Build messages with history
            messages = session.get_history_for_claude()
            
            if debug_mode:
                yield debug_event("api", "Built message history for Claude", {
                    "message_count": len(messages),
                    "model": self.model,
                })
            
            # Process response in a loop (for tool use)
            max_iterations = 10  # Safety limit
            iteration = 0
            final_content = ""
            all_streamed_text: List[str] = []  # Track ALL streamed text for skill extraction
            last_usage: Optional[Any] = None
            
            while iteration < max_iterations:
                iteration += 1
                
                if debug_mode:
                    yield debug_event("api", f"Claude API iteration {iteration}/{max_iterations}")

                if session.consume_cancel():
                    yield error_event("Run cancelled", "cancelled")
                    yield done_event()
                    break

                if self.run_deadline_seconds and (time.monotonic() - start_total) > self.run_deadline_seconds:
                    yield error_event(f"Run exceeded {self.run_deadline_seconds}s budget", "run_timeout")
                    yield done_event()
                    break
                
                # Stream the response for this iteration
                streamed_text: List[str] = []
                base_allowlist = set(self.allowed_tool_names) if self.allowed_tool_names else set(tool.get("name") for tool in ALL_TOOLS)
                tools_to_use = [tool for tool in ALL_TOOLS if tool.get("name") in base_allowlist]
                if tool_allowlist:
                    allow_set = set(tool_allowlist) & base_allowlist
                    tools_to_use = [tool for tool in ALL_TOOLS if tool.get("name") in allow_set]
                    if debug_mode:
                        yield debug_event("agent", "Tool allowlist applied", {"tools": list(allow_set)})
                
                tool_call_count = 0
                iter_start = time.monotonic()
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=4096,
                    system=system_blocks,
                    tools=tools_to_use,
                    messages=messages
                ) as stream:
                    for event in stream:
                        # Stream text deltas as they arrive
                        if getattr(event, "type", None) == "content_block_delta":
                            delta_text = getattr(event.delta, "text", None)
                            if delta_text:
                                # Heuristic: drop raw JSON-like blobs to avoid leaking tool payloads
                                stripped = delta_text.strip()
                                if not (len(stripped) > 200 and (stripped.startswith("{") or stripped.startswith("["))):
                                    streamed_text.append(delta_text)
                                    all_streamed_text.append(delta_text)  # Track for skill detection
                                    yield content_event(delta_text)
                    response = stream.get_final_message()
                    last_usage = getattr(response, "usage", None)

                if debug_mode and last_usage:
                    cache_read = getattr(last_usage, "cache_read_input_tokens", None)
                    cache_creation = getattr(last_usage, "cache_creation_input_tokens", None)
                    cache_status = "hit" if (cache_read or 0) > 0 else ("write" if (cache_creation or 0) > 0 else "none")
                    usage_payload = {
                        "cache_creation_input_tokens": getattr(last_usage, "cache_creation_input_tokens", None),
                        "cache_read_input_tokens": getattr(last_usage, "cache_read_input_tokens", None),
                        "input_tokens": getattr(last_usage, "input_tokens", None),
                        "output_tokens": getattr(last_usage, "output_tokens", None),
                        "cache_status": cache_status,
                        "model": self.model,
                        "agent_mode": agent_mode or agent_label or "single",
                        "skill_id": None,  # Claude-native routing, skill detected from response
                    }
                    yield debug_event("cache", "Claude usage (cache-aware)", usage_payload)
                
                yield thinking_event("query_analysis", "completed", "Question understood")
                yield plan_update_event("understand", "completed", "Question understood")
                
                # Check stop reason
                if response.stop_reason == "end_turn":
                    # Final response - add to session
                    final_content = "".join(streamed_text)
                    if not final_content:
                        for block in response.content:
                            if hasattr(block, 'text'):
                                final_content += block.text
                    break
                    
                elif response.stop_reason == "tool_use":
                    # Process tool calls
                    tool_results = []
                    tool_call_records = []
                    
                    if debug_mode:
                        tool_count = sum(1 for b in response.content if b.type == "tool_use")
                        yield debug_event("tool", f"Claude requested {tool_count} tool call(s)")
                    
                    for block in response.content:
                        if block.type == "tool_use":
                            tool_call_count += 1
                            tool_name = block.name
                            tool_input = block.input
                            tool_use_id = block.id
                            
                            if debug_mode:
                                yield debug_event("tool", f"Tool call: {tool_name}", {
                                    "tool_use_id": tool_use_id,
                                    "input_keys": list(tool_input.keys()) if isinstance(tool_input, dict) else None,
                                })
                            
                            if tool_name == "query_database":
                                yield plan_update_event("sql", "running", "Executing SQL query")
                            
                            tool_call_records.append({
                                "id": tool_use_id,
                                "name": tool_name,
                                "input": tool_input,
                            })
                            
                            yield thinking_event(
                                f"tool_{tool_name}",
                                "running",
                                f"Executing {tool_name}..."
                            )
                            yield tool_start_event(tool_name, tool_input)
                            
                            # Emit process node for tool execution
                            tool_node_id = f"tool_{tool_use_id}"
                            yield process_node_event(
                                node_id=tool_node_id,
                                node_type="tool",
                                label=tool_name.replace("_", " ").title(),
                                status="running",
                                parent_id="claude_api",
                                description=f"Executing tool: {tool_name}",
                                data={"tool_input_keys": list(tool_input.keys()) if isinstance(tool_input, dict) else []},
                            )
                            yield process_edge_event("claude_api", tool_node_id, label="tool call", animated=True)
                            
                            # Execute the tool
                            tool_start_time = time.monotonic()
                            if is_web_search_tool(tool_name):
                                # Web search is handled by Claude - result comes back in next response
                                result = {"success": True, "type": "server_tool"}
                                if debug_mode:
                                    yield debug_event("tool", f"{tool_name} is server-handled tool")
                            else:
                                if debug_mode:
                                    yield debug_event("tool", f"Executing local tool: {tool_name}")
                                result = await self._execute_tool(tool_name, tool_input)
                                if debug_mode:
                                    yield debug_event("tool", f"Tool {tool_name} completed", {
                                        "success": result.get("success", False),
                                        "error": result.get("error") if not result.get("success") else None,
                                    })
                            
                            duration_ms = int((time.monotonic() - tool_start_time) * 1000)
                            result_with_timing = dict(result)
                            result_with_timing["duration_ms"] = duration_ms
                            yield tool_end_event(tool_name, result_with_timing, result.get("success", True))
                            yield thinking_event(
                                f"tool_{tool_name}",
                                "completed" if result.get("success", True) else "error",
                                f"{tool_name} completed" if result.get("success", True) else f"{tool_name} failed: {result.get('error', 'Unknown error')}"
                            )

                            # Emit showcase artifact link for frontend embedding
                            if (
                                tool_name == "open_showcase_page"
                                and result.get("success")
                                and result.get("url")
                            ):
                                yield html_artifact_event(
                                    result.get("url"),
                                    result.get("title", "Project Showcase"),
                                    result.get("description", "Interactive overview of the Next Gen Analytics project."),
                                )
                            
                            # Update tool process node
                            yield process_update_event(
                                node_id=tool_node_id,
                                status="completed" if result.get("success", True) else "error",
                                summary=f"{tool_name} {'succeeded' if result.get('success', True) else 'failed'}",
                                data={"duration_ms": duration_ms},
                            )
                            
                            # Send chart or data events if applicable
                            if tool_name == "generate_echarts" and result.get("success"):
                                yield plan_update_event("visualize", "running", "Preparing chart")
                                yield chart_event(result.get("config", {}))
                                yield plan_update_event(
                                    "visualize",
                                    "completed",
                                    result.get("chart_type", "chart"),
                                )
                            elif tool_name == "create_tradingview_chart" and result.get("success"):
                                yield plan_update_event("visualize", "running", "Preparing TradingView chart")
                                yield chart_event(result.get("config", {}))
                                yield plan_update_event("visualize", "completed", "TradingView chart ready")
                            elif tool_name == "query_database" and result.get("success"):
                                yield data_event(
                                    result.get("rows", [])[:50],  # Limit rows sent
                                    result.get("columns", []),
                                    result.get("sql"),  # Include SQL for transparency widget
                                )
                                yield plan_update_event(
                                    "sql",
                                    "completed",
                                    f"Rows: {len(result.get('rows', []))}",
                                )
                            elif tool_name == "get_news_sentiment" and result.get("success"):
                                yield news_event(
                                    result.get("articles", []),
                                    result.get("ticker", ""),
                                    result.get("aggregate_sentiment", 0),
                                    result.get("aggregate_label", "Neutral"),
                                )
                                yield plan_update_event(
                                    "analysis",
                                    "running",
                                    f"News: {result.get('article_count', 0)} articles",
                                )
                            
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                # Claude requires non-empty content for every message; avoid empty strings.
                                # Always serialize result (even for server-side web_search) to keep content non-empty.
                                # Use default=str to serialize dates/decimals safely
                                "content": json.dumps(result, default=str),
                            })
                    
                    # Continue conversation with tool results
                    assistant_content = response.content if response.content else [{"type": "text", "text": "(tool call)"}]
                    if tool_results:
                        messages.append({"role": "assistant", "content": assistant_content})
                        messages.append({"role": "user", "content": tool_results})
                        
                        # Persist tool calls/results for future turns (with non-empty content)
                        session.add_message(
                            "assistant",
                            json.dumps(tool_call_records, default=str),
                            tool_calls=tool_call_records,
                        )
                        session.add_message(
                            "user",
                            json.dumps(tool_results, default=str),
                            tool_results=tool_results,
                        )
                    else:
                        # No tool results produced; avoid sending empty content to Claude
                        if debug_mode:
                            yield debug_event("tool", "No tool results returned; aborting tool loop")
                        break
                    
                    yield thinking_event("generating_response", "running", "Generating response...")
                    continue
                else:
                    # Unknown stop reason
                    logger.warning("Unknown stop reason: %s", response.stop_reason)
                    break
            
            # Add assistant response to history
            if final_content:
                session.add_message("assistant", final_content)
            
            # Extract skill from response and emit skill_event if detected
            # Use all_streamed_text since the [SKILL:] marker may come in early iterations
            full_streamed_content = "".join(all_streamed_text)
            detected_skill_id = extract_skill_from_response(full_streamed_content)
            if detected_skill_id:
                detected_skill = get_skill_by_id(detected_skill_id)
                if detected_skill:
                    skill_download_url = f"/api/conversational-analytics/skills/{detected_skill.filename}"
                    yield skill_event(detected_skill_id, detected_skill.name, skill_download_url)
                    if debug_mode:
                        yield debug_event("skill", f"Detected skill: {detected_skill.name}", {
                            "skill_id": detected_skill_id,
                            "filename": detected_skill.filename,
                        })
            
            # Emit final output node
            yield process_node_event(
                node_id="response_generated",
                node_type="output",
                label="Response Generated",
                status="completed",
                parent_id="claude_api",
                description="Final response ready for user",
            )
            yield process_edge_event("claude_api", "response_generated", label="response", animated=False)
            yield process_update_event("claude_api", "completed", "Analysis complete")
            
            yield thinking_event("generating_response", "completed", "Response ready")
            yield plan_update_event("analysis", "completed", "Answer ready")
            yield done_event()
            if debug_mode:
                elapsed_ms = int((time.monotonic() - start_total) * 1000)
                if last_usage:
                    cache_read = getattr(last_usage, "cache_read_input_tokens", None)
                    cache_creation = getattr(last_usage, "cache_creation_input_tokens", None)
                    cache_status = "hit" if (cache_read or 0) > 0 else ("write" if (cache_creation or 0) > 0 else "none")
                    yield debug_event("cache", "Final Claude usage (cache-aware)", {
                        "cache_creation_input_tokens": getattr(last_usage, "cache_creation_input_tokens", None),
                        "cache_read_input_tokens": getattr(last_usage, "cache_read_input_tokens", None),
                        "input_tokens": getattr(last_usage, "input_tokens", None),
                        "output_tokens": getattr(last_usage, "output_tokens", None),
                        "cache_status": cache_status,
                        "model": self.model,
                        "agent_mode": agent_mode or agent_label or "single",
                        "skill_id": None,  # Claude-native routing
                    })
                yield debug_event("tool", "Tool/flow stats", {
                    "tool_call_count": tool_call_count,
                    "elapsed_ms": elapsed_ms,
                })
            
        except anthropic.APIError as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error("Claude API error: %s", e)
            if debug_mode:
                yield debug_event("error", f"Claude API error: {str(e)}", {
                    "error_type": type(e).__name__,
                    "traceback": error_details,
                })
            # Surface error to thinking panel
            yield thinking_event("api_error", "error", f"API error: {str(e)}")
            yield error_event(f"API error: {str(e)}", "api_error", error_details if debug_mode else "")
            yield done_event()
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error("Agent error: %s\n%s", e, error_details)
            if debug_mode:
                yield debug_event("error", f"Agent error: {str(e)}", {
                    "error_type": type(e).__name__,
                    "traceback": error_details,
                })
            # Surface error to thinking panel
            yield thinking_event("agent_error", "error", f"Error: {str(e)}")
            yield error_event(f"Error: {str(e)}", "agent_error", error_details if debug_mode else "")
            yield done_event()
        finally:
            clear_run_context()

    def _get_tool_timeout(self, tool_name: str) -> Optional[float]:
        """Function: _get_tool_timeout — returns the timeout for a tool based on settings.json.
        Called from: _execute_tool to enforce per-tool deadlines.
        Invokes: cached sdk settings for default/per-tool values.
        Purpose: Enables consistent tool timeouts aligned with SDK configuration."""
        if self.per_tool_timeout:
            value = self.per_tool_timeout.get(tool_name)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None
        if self.default_tool_timeout:
            try:
                return float(self.default_tool_timeout)
            except (TypeError, ValueError):
                return None
        return None
    
    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Function: _execute_tool — invoked by run_with_tools to dispatch domain tools.
        Called from: run_with_tools after a Claude tool_use event.
        Invokes: TOOL_EXECUTORS registry to execute the requested tool.
        Purpose: Centralizes tool execution and error handling for conversational analytics."""
        if self.tool_failures.get(tool_name, 0) >= self.max_tool_failures:
            return {"success": False, "error": f"{tool_name} temporarily blocked after repeated failures"}

        executor = TOOL_EXECUTORS.get(tool_name)
        if not executor:
            logger.warning("Unknown tool requested: %s", tool_name)
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        try:
            # Execute the tool (all are async)
            timeout = self._get_tool_timeout(tool_name)
            coro = executor(**tool_input)
            result = await asyncio.wait_for(coro, timeout=timeout) if timeout else await coro
            # Reset circuit breaker on success
            self.tool_failures[tool_name] = 0
            return result
        except asyncio.TimeoutError:
            self.tool_failures[tool_name] = self.tool_failures.get(tool_name, 0) + 1
            logger.warning("Tool execution timeout (%s) after %ss", tool_name, timeout)
            return {
                "success": False,
                "error": f"{tool_name} timed out after {timeout}s",
            }
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error("Tool execution error (%s): %s\n%s", tool_name, e, error_details)
            self.tool_failures[tool_name] = self.tool_failures.get(tool_name, 0) + 1
            return {
                "success": False,
                "error": str(e),
                "traceback": error_details if settings.debug_mode else None,
            }


_agent_instance: Optional[ConversationalAnalyticsAgent] = None


def get_conversational_analytics_agent() -> ConversationalAnalyticsAgent:
    """Function: get_conversational_analytics_agent — called from conversational_analytics.routes.chat endpoints to obtain a singleton agent.
    Invokes: ConversationalAnalyticsAgent() once dependencies are verified.
    Purpose: Lazily initialize the agent so FastAPI routes stay importable even when optional deps are missing."""
    global _agent_instance
    if _anthropic_import_error:
        raise MissingDependencyError(
            "Conversational Analytics requires the 'anthropic' package. "
            "Run `pip install -r backend/requirements.txt` to enable the agent."
        ) from _anthropic_import_error
    if _agent_instance is None:
        _agent_instance = ConversationalAnalyticsAgent()
    return _agent_instance
