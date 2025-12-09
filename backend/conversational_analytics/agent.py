"""Conversational Analytics Agent - Claude-powered single agent with tool use."""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

try:
    import anthropic  # type: ignore
    _anthropic_import_error: Optional[ImportError] = None
except ImportError as exc:  # pragma: no cover - optional dependency
    anthropic = None  # type: ignore
    _anthropic_import_error = exc

from .config import settings
from .memory import session_store
from .tools import ALL_TOOLS, TOOL_EXECUTORS, is_web_search_tool, format_web_search_results
from .skills import select_skill, load_skill_content
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
    debug_event,
)

logger = logging.getLogger(__name__)

# System prompt for the agent
SYSTEM_PROMPT = """You are a conversational analytics assistant specialized in financial data analysis for semiconductor companies.

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

Be conversational, accurate, and insightful. Always cite the data source when using web search."""


class MissingDependencyError(RuntimeError):
    """Raised when required third-party dependencies are unavailable."""


class ConversationalAnalyticsAgent:
    """Single agent for conversational analytics with Claude."""
    
    def __init__(self):
        if anthropic is None or _anthropic_import_error:
            raise MissingDependencyError(
                "Conversational Analytics requires the 'anthropic' package. "
                "Install backend dependencies (pip install -r backend/requirements.txt)."
            ) from _anthropic_import_error
        self.client = anthropic.Anthropic(api_key=settings.claude_api_key)
        self.model = settings.claude_model
        
    async def run_with_tools(
        self,
        message: str,
        session_id: str
    ) -> AsyncGenerator[str, None]:
        """Function: run_with_tools — called from conversational_analytics.routes.chat stream_chat/chat endpoints to drive SSE responses.
        Invokes: session_store for history, Anthropic streaming, and TOOL_EXECUTORS to emit SSE events.
        Purpose: Orchestrates Claude + tool use for conversational analytics conversations and streams client-facing events.
        """
        debug_mode = settings.debug_mode
        
        # Debug: Session initialization
        if debug_mode:
            yield debug_event("session", f"Getting/creating session: {session_id}")
        
        # Get or create session
        session = session_store.get_or_create(session_id)
        
        if debug_mode:
            yield debug_event("session", "Session ready", {
                "session_id": session_id,
                "history_count": len(session.messages),
            })
        
        # Add user message to history
        session.add_message("user", message)
        
        if debug_mode:
            yield debug_event("agent", f"User message received ({len(message)} chars)")

        # Detect applicable skill and build augmented system prompt
        selected_skill = select_skill(message)
        system_prompt = SYSTEM_PROMPT
        if selected_skill:
            skill_text = load_skill_content(selected_skill)
            system_prompt = f"{SYSTEM_PROMPT}\n\nSkill Activated: {selected_skill.name} (id: {selected_skill.skill_id})\nFollow this guidance:\n{skill_text}"
            skill_download_url = f"/api/conv-analytics/skills/{selected_skill.skill_id}"
            yield skill_event(selected_skill.skill_id, selected_skill.name, skill_download_url)
            if debug_mode:
                yield debug_event("agent", f"Skill selected: {selected_skill.skill_id}", {"skill": selected_skill.skill_id})
        
        yield status_event("Connecting to Claude...")
        plan_steps = [
            {"id": "understand", "label": "Understand question", "status": "running"},
            {"id": "sql", "label": "Query comp_financials", "status": "pending"},
            {"id": "visualize", "label": "Build chart", "status": "pending"},
            {"id": "analysis", "label": "Summarize insights", "status": "pending"},
        ]
        yield plan_event(plan_steps)
        yield thinking_event("query_analysis", "running", "Analyzing your question...")
        
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
            
            while iteration < max_iterations:
                iteration += 1
                
                if debug_mode:
                    yield debug_event("api", f"Claude API iteration {iteration}/{max_iterations}")
                
                # Stream the response for this iteration
                streamed_text: List[str] = []
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=4096,
                    system=system_prompt,
                    tools=ALL_TOOLS,
                    messages=messages
                ) as stream:
                    for event in stream:
                        # Stream text deltas as they arrive
                        if getattr(event, "type", None) == "content_block_delta":
                            delta_text = getattr(event.delta, "text", None)
                            if delta_text:
                                streamed_text.append(delta_text)
                                yield content_event(delta_text)
                    response = stream.get_final_message()
                
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
                            
                            # Execute the tool
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
                            
                            yield tool_end_event(tool_name, result, result.get("success", True))
                            yield thinking_event(
                                f"tool_{tool_name}",
                                "completed" if result.get("success", True) else "error",
                                f"{tool_name} completed" if result.get("success", True) else f"{tool_name} failed: {result.get('error', 'Unknown error')}"
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
                                    result.get("columns", [])
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
            
            yield thinking_event("generating_response", "completed", "Response ready")
            yield plan_update_event("analysis", "completed", "Answer ready")
            yield done_event()
            
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
    
    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Function: _execute_tool — invoked by run_with_tools to dispatch domain tools.
        Called from: run_with_tools after a Claude tool_use event.
        Invokes: TOOL_EXECUTORS registry to execute the requested tool.
        Purpose: Centralizes tool execution and error handling for conversational analytics."""
        executor = TOOL_EXECUTORS.get(tool_name)
        if not executor:
            logger.warning("Unknown tool requested: %s", tool_name)
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        try:
            # Execute the tool (all are async)
            result = await executor(**tool_input)
            return result
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error("Tool execution error (%s): %s\n%s", tool_name, e, error_details)
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
