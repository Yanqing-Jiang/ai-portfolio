"""Conversational Analytics Agent - Claude-powered single agent with tool use."""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Dict, List

import anthropic

from .config import settings
from .memory import session_store
from .tools import ALL_TOOLS, TOOL_EXECUTORS, is_web_search_tool, format_web_search_results
from .streaming import (
    status_event,
    thinking_event,
    tool_start_event,
    tool_end_event,
    content_event,
    chart_event,
    data_event,
    done_event,
    error_event,
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

Format numbers as: $1.2B (billions), $150M (millions), 15.3% (percentages)

Be conversational, accurate, and insightful. Always cite the data source when using web search."""


class ConversationalAnalyticsAgent:
    """Single agent for conversational analytics with Claude."""
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.claude_api_key)
        self.model = settings.claude_model
        
    async def run_with_tools(
        self,
        message: str,
        session_id: str
    ) -> AsyncGenerator[str, None]:
        """Run the agent with tools and stream responses.
        
        Args:
            message: User's message
            session_id: Session identifier
            
        Yields:
            SSE formatted event strings
        """
        # Get or create session
        session = session_store.get_or_create(session_id)
        
        # Add user message to history
        session.add_message("user", message)
        
        yield status_event("Connecting to Claude...")
        yield thinking_event("query_analysis", "running", "Analyzing your question...")
        
        try:
            # Build messages with history
            messages = session.get_history_for_claude()
            
            # Initial call to Claude with all tools
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=ALL_TOOLS,
                messages=messages
            )
            
            yield thinking_event("query_analysis", "completed", "Question understood")
            
            # Process response in a loop (for tool use)
            max_iterations = 10  # Safety limit
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                
                # Check stop reason
                if response.stop_reason == "end_turn":
                    # Final response - extract and stream content
                    for block in response.content:
                        if hasattr(block, 'text'):
                            yield content_event(block.text)
                    break
                    
                elif response.stop_reason == "tool_use":
                    # Process tool calls
                    tool_results = []
                    
                    for block in response.content:
                        if block.type == "tool_use":
                            tool_name = block.name
                            tool_input = block.input
                            tool_use_id = block.id
                            
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
                            else:
                                result = await self._execute_tool(tool_name, tool_input)
                            
                            yield tool_end_event(tool_name, result, result.get("success", True))
                            yield thinking_event(
                                f"tool_{tool_name}",
                                "completed",
                                f"{tool_name} completed"
                            )
                            
                            # Send chart or data events if applicable
                            if tool_name == "generate_echarts" and result.get("success"):
                                yield chart_event(result.get("config", {}))
                            elif tool_name == "create_tradingview_chart" and result.get("success"):
                                yield chart_event(result.get("config", {}))
                            elif tool_name == "query_database" and result.get("success"):
                                yield data_event(
                                    result.get("rows", [])[:50],  # Limit rows sent
                                    result.get("columns", [])
                                )
                            
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": json.dumps(result) if not is_web_search_tool(tool_name) else ""
                            })
                    
                    # Continue conversation with tool results
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": tool_results})
                    
                    yield thinking_event("generating_response", "running", "Generating response...")
                    
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=4096,
                        system=SYSTEM_PROMPT,
                        tools=ALL_TOOLS,
                        messages=messages
                    )
                else:
                    # Unknown stop reason
                    logger.warning("Unknown stop reason: %s", response.stop_reason)
                    break
            
            # Add assistant response to history
            final_content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    final_content += block.text
            if final_content:
                session.add_message("assistant", final_content)
            
            yield thinking_event("generating_response", "completed", "Response ready")
            yield done_event()
            
        except anthropic.APIError as e:
            logger.error("Claude API error: %s", e)
            yield error_event(f"API error: {str(e)}", "api_error")
            yield done_event()
        except Exception as e:
            logger.error("Agent error: %s", e)
            yield error_event(f"Error: {str(e)}", "agent_error")
            yield done_event()
    
    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with given input.
        
        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool
            
        Returns:
            Tool execution result
        """
        executor = TOOL_EXECUTORS.get(tool_name)
        if not executor:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        try:
            # Execute the tool (all are async)
            result = await executor(**tool_input)
            return result
        except Exception as e:
            logger.error("Tool execution error (%s): %s", tool_name, e)
            return {"success": False, "error": str(e)}
