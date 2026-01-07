"""
SDK Flow Integration - Official Claude Agent SDK Pattern

Module: sdk_flow.py
Role: Execute A2UI skills using Claude Agent SDK with automatic MCP tool execution.
Called from: A2UIRuntime.stream_dashboard (when USE_SDK_FLOW=true)
Invokes: ClaudeSDKClient with MCP tools (query_database, get_news_sentiment, generate_analysis)
Why: Enables true agent behavior - LLM autonomously calls tools and sees results.

Architecture:
1. ClaudeSDKClient maintains session with MCP tools registered
2. LLM receives skill.md instructions + user query
3. LLM autonomously calls tools (SDK executes them automatically)
4. LLM sees tool results and generates A2UI-formatted response
5. We parse the response and emit A2UI messages

Reference: https://platform.claude.com/docs/en/agent-sdk/python
"""

from __future__ import annotations
from typing import AsyncGenerator, Dict, Any, List, Optional
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# SDK imports with availability check
try:
    from claude_agent_sdk import (
        ClaudeSDKClient,
        ClaudeAgentOptions,
        create_sdk_mcp_server,
        AssistantMessage,
        TextBlock,
        ToolUseBlock,
        ToolResultBlock,
        ResultMessage,
    )
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    ClaudeSDKClient = None
    ClaudeAgentOptions = None
    create_sdk_mcp_server = None
    AssistantMessage = None
    TextBlock = None
    ToolUseBlock = None
    ToolResultBlock = None
    ResultMessage = None


class A2UISDKFlow:
    """
    Implements official Claude Agent SDK flow where LLM drives tool execution.
    
    Class: A2UISDKFlow
    Role: Execute skills with full LLM autonomy over tool usage and A2UI generation.
    Called from: A2UIRuntime (when SDK mode is enabled)
    Invokes: ClaudeSDKClient with registered MCP tools
    Why: True agent behavior - LLM calls tools, sees data, and crafts intelligent responses.
    
    Key Pattern:
    - Uses ClaudeSDKClient for session continuity
    - Registers A2UI MCP tools via create_sdk_mcp_server()
    - SDK automatically executes tools when LLM requests them
    - We only need to process final AssistantMessage content
    """
    
    def __init__(self):
        """
        Initialize SDK Flow.
        
        No sdk_wrapper needed - we use ClaudeSDKClient directly.
        """
        from .config import get_settings
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
        self._skills_dir = Path(__file__).parent.parent.parent / ".claude" / "skills"
        self._mcp_server = None
    
    def is_available(self) -> bool:
        """Check if Claude Agent SDK is available."""
        return SDK_AVAILABLE and ClaudeSDKClient is not None
    
    def _get_mcp_server(self):
        """
        Create or return cached MCP server with A2UI tools.
        
        Function: _get_mcp_server
        Called from: execute_with_skill_context
        Invokes: create_sdk_mcp_server with A2UI tools
        Why: Registers tools that SDK can execute automatically.
        """
        if self._mcp_server is not None:
            return self._mcp_server
        
        if not SDK_AVAILABLE or create_sdk_mcp_server is None:
            return None
        
        from .mcp_tools import A2UI_MCP_TOOLS, SDK_TOOL_AVAILABLE
        
        if not SDK_TOOL_AVAILABLE or not A2UI_MCP_TOOLS:
            self.logger.warning("A2UI MCP tools not available")
            return None
        
        # Create MCP server with our tools
        self._mcp_server = create_sdk_mcp_server(
            name="a2ui",
            version="1.0.0",
            tools=A2UI_MCP_TOOLS,
        )
        
        self.logger.info(f"Created A2UI MCP server with {len(A2UI_MCP_TOOLS)} tools")
        return self._mcp_server

    def _resolve_cli_path(self) -> Optional[str]:
        """
        Resolve the Claude CLI path for SDK flow execution.
        
        Function: _resolve_cli_path
        Called from: execute_with_skill_context
        Invokes: os.path, Path
        Why: Forces SDK flow to use the npm-installed Claude CLI on Windows.
        """
        import os
        
        if os.name != "nt":
            return None
        
        npm_claude = os.path.expandvars(r"%APPDATA%\npm\claude.cmd")
        if os.path.exists(npm_claude):
            return npm_claude
        
        return None
    
    def load_skill_content(self, skill_id: str) -> Optional[str]:
        """
        Load skill.md content for a given skill ID.
        
        Function: load_skill_content
        Called from: execute_with_skill_context
        Why: Injects skill instructions into LLM context.
        """
        # Convert skill_id format (a2ui_peer_compare -> a2ui-peer-compare)
        skill_dir_name = skill_id.replace("_", "-")
        skill_path = self._skills_dir / skill_dir_name / "skill.md"
        
        if not skill_path.exists():
            self.logger.warning(f"Skill file not found: {skill_path}")
            return None
        
        try:
            return skill_path.read_text(encoding="utf-8")
        except Exception as e:
            self.logger.error(f"Failed to read skill file: {e}")
            return None
    
    def _build_system_prompt(
        self,
        skill_content: str,
        parameters: Dict[str, Any],
    ) -> str:
        """
        Build system prompt with skill instructions and A2UI output format.
        
        Function: _build_system_prompt
        Called from: execute_with_skill_context
        Why: Provides LLM with skill context and output contract.
        """
        tickers = parameters.get("tickers", [])
        metric = parameters.get("metric", "Revenue")
        time_range = parameters.get("time_range", "3M")
        
        return f"""You are a financial data analyst assistant with access to tools.

## Skill Instructions
{skill_content}

## Current Context
- Tickers: {', '.join(tickers) if tickers else 'Not specified'}
- Metric: {metric}
- Time Range: {time_range}

## Available Tools
You have access to the following MCP tools:
1. `mcp__a2ui__query_database` - Execute SQL queries against the financial database
2. `mcp__a2ui__get_news_sentiment` - Fetch news with sentiment for a ticker
3. `mcp__a2ui__generate_analysis` - Generate AI analysis narratives

## Output Format
After gathering data with tools, provide your final response with:
1. A brief summary of your findings
2. Key data points in this JSON structure (wrapped in ```json code fence):

```json
{{
  "data": {{
    "kpis": {{
      "revenue": <number>,
      "net_income": <number>,
      "gross_margin": <percentage>,
      "operating_margin": <percentage>
    }},
    "chart": {{
      "series": [
        {{"name": "<metric>", "data": [<values>]}}
      ]
    }},
    "explanation": "<your analysis summary>",
    "factors": [
      {{"text": "<factor description>", "impact": "positive|negative|neutral", "icon": "📊|📈|📉|💰"}}
    ]
  }},
  "follow_ups": [
    "<suggested follow-up question 1>",
    "<suggested follow-up question 2>"
  ]
}}
```

Always use the tools to fetch real data before responding. Do not make up data."""
    
    async def execute_with_skill_context(
        self,
        skill_id: str,
        user_query: str,
        parameters: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute skill with full SDK flow - LLM drives everything.
        
        Function: execute_with_skill_context
        Called from: A2UIRuntime.stream_dashboard (when SDK mode enabled)
        Invokes: ClaudeSDKClient with MCP tools
        Why: Enables intelligent, data-aware A2UI component generation.
        
        Args:
            skill_id: ID of the skill to execute
            user_query: User's original question
            parameters: Extracted slots (tickers, metric, etc.)
        
        Yields:
            A2UI message chunks (audit events, data_update, surface_update)
        """
        if not self.is_available():
            yield {"type": "error", "message": "Claude Agent SDK not available"}
            return
        
        # Load skill instructions
        skill_content = self.load_skill_content(skill_id)
        if not skill_content:
            yield {"type": "error", "message": f"Skill not found: {skill_id}"}
            return
        
        # Get MCP server with tools
        mcp_server = self._get_mcp_server()
        if not mcp_server:
            yield {"type": "error", "message": "MCP tools not available"}
            return
        
        # Build system prompt with skill context
        system_prompt = self._build_system_prompt(skill_content, parameters)
        
        yield {
            "type": "audit",
            "event": "sdk_flow_started",
            "details": f"Executing {skill_id} with SDK flow",
        }
        
        try:
            # Configure ClaudeSDKClient options
            cli_path = self._resolve_cli_path()
            if cli_path:
                self.logger.info("SDK Flow using Claude CLI path: %s", cli_path)
            else:
                self.logger.info("SDK Flow using default Claude CLI resolution")
            
            options_kwargs: Dict[str, Any] = {
                "system_prompt": system_prompt,
                "mcp_servers": {"a2ui": mcp_server},
                "allowed_tools": [
                    "mcp__a2ui__query_database",
                    "mcp__a2ui__get_news_sentiment",
                    "mcp__a2ui__generate_analysis",
                ],
            }
            if cli_path:
                options_kwargs["cli_path"] = cli_path
            
            options = ClaudeAgentOptions(**options_kwargs)
            
            # Use ClaudeSDKClient for automatic tool execution
            async with ClaudeSDKClient(options=options) as client:
                yield {
                    "type": "audit",
                    "event": "sdk_session_started",
                    "details": "ClaudeSDKClient connected",
                }
                
                # Send the user query
                await client.query(user_query)
                
                # Collect response
                full_response_text = ""
                tool_calls_made = []
                tool_results = []
                
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                full_response_text += block.text
                            elif isinstance(block, ToolUseBlock):
                                tool_calls_made.append({
                                    "id": block.id,
                                    "name": block.name,
                                    "input": block.input,
                                })
                                yield {
                                    "type": "audit",
                                    "event": "tool_called",
                                    "details": f"LLM called {block.name}",
                                }
                            elif ToolResultBlock is not None and isinstance(block, ToolResultBlock):
                                tool_results.append({
                                    "tool_use_id": block.tool_use_id,
                                    "content": block.content,
                                    "is_error": block.is_error,
                                })
                                yield {
                                    "type": "audit",
                                    "event": "tool_completed",
                                    "details": f"Tool returned result",
                                }
                    elif ResultMessage is not None and isinstance(message, ResultMessage):
                        # Conversation complete
                        yield {
                            "type": "audit",
                            "event": "sdk_conversation_complete",
                            "details": f"Tools called: {len(tool_calls_made)}, Results: {len(tool_results)}",
                        }
                
                # Parse the final response for A2UI data
                if full_response_text:
                    a2ui_output = self._parse_a2ui_output(full_response_text)
                    
                    if a2ui_output:
                        # Emit data update
                        if "data" in a2ui_output:
                            yield {
                                "type": "data_update",
                                "data": a2ui_output["data"],
                                "path": "/data",
                            }
                        
                        # Emit follow-ups
                        if "follow_ups" in a2ui_output:
                            yield {
                                "type": "follow_ups",
                                "suggestions": a2ui_output["follow_ups"],
                            }
                    else:
                        # Try to extract any useful data from raw text
                        yield {
                            "type": "data_update",
                            "data": {
                                "explanation": full_response_text[:1000],
                                "sdk_raw_response": True,
                            },
                            "path": "/data",
                        }
                
                yield {"type": "done", "success": True}
                
        except Exception as e:
            self.logger.error(f"SDK flow execution failed: {e}", exc_info=True)
            yield {"type": "error", "message": str(e)}
    
    def _parse_a2ui_output(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse A2UI JSON from LLM response.
        
        Function: _parse_a2ui_output
        Called from: execute_with_skill_context
        Why: Extracts structured data from LLM's response for A2UI rendering.
        """
        if not response_text:
            return None
        
        # Try to extract JSON from code fence
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text, re.IGNORECASE)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError as e:
                self.logger.warning(f"Failed to parse A2UI JSON from code fence: {e}")
        
        # Try to find raw JSON object
        brace_match = re.search(r'\{[\s\S]*"data"[\s\S]*\}', response_text)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass
        
        self.logger.warning("Could not parse A2UI JSON from response")
        return None


# ============================================================================
# Factory Function
# ============================================================================

def create_sdk_flow() -> Optional[A2UISDKFlow]:
    """
    Create an SDK flow instance if available.
    
    Function: create_sdk_flow
    Called from: A2UIRuntime initialization
    Why: Factory pattern for optional SDK flow creation.
    
    Returns:
        A2UISDKFlow instance if SDK is available, None otherwise.
    """
    flow = A2UISDKFlow()
    if flow.is_available():
        logger.info("SDK Flow created successfully")
        return flow
    else:
        logger.warning("SDK Flow unavailable - Claude Agent SDK not installed")
        return None


# ============================================================================
# Follow-up Generation (Optional Enhancement)
# ============================================================================

async def generate_llm_follow_ups(
    skill_id: str,
    data_model: Dict[str, Any],
    max_suggestions: int = 4,
) -> List[str]:
    """
    Generate contextual follow-up suggestions using LLM.
    
    Function: generate_llm_follow_ups
    Called from: routes/dashboard.py get_follow_up_suggestions
    Why: Provides intelligent, data-aware follow-up suggestions.
    
    Args:
        skill_id: Current skill ID for context
        data_model: Current dashboard data
        max_suggestions: Maximum number of suggestions
    
    Returns:
        List of follow-up question strings.
    """
    if not SDK_AVAILABLE:
        return _fallback_follow_ups(skill_id, data_model)
    
    try:
        # Build prompt for follow-up generation
        prompt = f"""Based on this financial analysis:
Skill: {skill_id}
Data Summary: {json.dumps(data_model.get('data', {}), default=str)[:500]}

Generate {max_suggestions} follow-up questions a user might ask.
Return as JSON array: ["question1", "question2", ...]"""
        
        from claude_agent_sdk import query, ClaudeAgentOptions
        
        options = ClaudeAgentOptions(
            system_prompt="You are a financial analyst. Generate relevant follow-up questions.",
        )
        
        full_response = ""
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        full_response += block.text
        
        # Parse JSON array from response
        json_match = re.search(r'\[[\s\S]*?\]', full_response)
        if json_match:
            return json.loads(json_match.group(0))[:max_suggestions]
        
    except Exception as e:
        logger.warning(f"LLM follow-up generation failed: {e}")
    
    return _fallback_follow_ups(skill_id, data_model)


def _fallback_follow_ups(skill_id: str, data_model: Dict[str, Any]) -> List[str]:
    """
    Generate rule-based follow-up suggestions.
    
    Function: _fallback_follow_ups
    Called from: generate_llm_follow_ups (on failure)
    Why: Provides reasonable suggestions without LLM.
    """
    tickers = data_model.get("tickers", [])
    primary = tickers[0] if tickers else "the stock"
    
    skill_suggestions = {
        "a2ui_explain_move": [
            f"What are analysts saying about {primary}?",
            f"Compare {primary} to its competitors",
            f"Show {primary} revenue trend",
        ],
        "a2ui_peer_compare": [
            f"Explain {primary} stock movement",
            "Which company has the best margins?",
            "Show quarterly revenue breakdown",
        ],
        "a2ui_margin_analysis": [
            f"Compare {primary} margins to peers",
            f"What drove {primary} margin changes?",
            "Show margin trend over time",
        ],
        "a2ui_revenue_trend": [
            f"Explain {primary} growth drivers",
            f"Compare {primary} revenue to peers",
            "What's the earnings outlook?",
        ],
    }
    
    return skill_suggestions.get(skill_id, [
        "Tell me more about this company",
        "Compare to competitors",
        "What's the outlook?",
    ])


__all__ = [
    "A2UISDKFlow",
    "create_sdk_flow",
    "generate_llm_follow_ups",
    "SDK_AVAILABLE",
]
