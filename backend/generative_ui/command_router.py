"""
Command Router - LLM-driven intent classification for conversational control.

Class: CommandRouter
Called from: dashboard routes (create, action, follow-up)
Invokes: Anthropic Messages API with tool calling
Why: Eliminates hardcoded keyword matching; lets LLM decide user intent.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
import logging

from .sdk_wrapper import A2UISDKWrapper, get_sdk_wrapper
from .conversation_state import get_conversation_store

logger = logging.getLogger(__name__)


class IntentClassification(BaseModel):
    """
    Structured output from intent classification.
    
    Class: IntentClassification
    Called from: CommandRouter.classify_intent
    Why: Provides typed structure for routing decisions.
    """
    intent: Literal[
        "new_analysis",      # Create new dashboard with new skill
        "modify_layout",     # Change layout, reorder, hide/show widgets
        "modify_data",       # Refine analysis (add ticker, change timeframe)
        "switch_component",  # Change visualization type
        "follow_up",         # Continue conversation on current dashboard
        "clarification",     # User responding to a clarification request
        "unknown"            # Cannot determine intent
    ]
    action_name: Optional[str] = None   # For modify_* intents
    action_params: Dict[str, Any] = Field(default_factory=dict)
    should_continue: bool = True        # Continue on current dashboard?
    rationale: str = ""                 # LLM's reasoning
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score 0.0-1.0")


# Confidence threshold below which we ask for clarification
CONFIDENCE_THRESHOLD = 0.7


# Tool definitions for Claude intent classification
INTENT_TOOLS = [
    {
        "name": "new_analysis",
        "description": """
        Create a completely new analysis dashboard. Use this when the user:
        - Asks about a new topic or ticker not currently being analyzed
        - Requests a different type of analysis (e.g., switch from margins to revenue)
        - Says "start over", "new analysis", or makes completely unrelated query
        - Mentions a ticker that is NOT in the current context
        
        Examples: "Analyze AMD", "Show me TSLA revenue", "New analysis for MSFT"
        """,
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The user's full query"},
                "rationale": {"type": "string", "description": "Why this is a new analysis"}
            },
            "required": ["query", "rationale"]
        }
    },
    {
        "name": "modify_layout",
        "description": """
        Modify the current dashboard's layout WITHOUT changing the data.
        Use this when the user:
        - Wants to reorder components (e.g., "put KPIs on top", "move chart to bottom")
        - Wants to hide/show widgets (e.g., "hide the news", "show the table")
        - Wants to change emphasis (e.g., "focus on the chart", "make the table bigger")
        - Wants to change the overall layout structure
        
        Examples: "Put the KPIs at the top", "Hide the news section", "Focus on charts"
        """,
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["reorder_widgets", "toggle_widget", "set_emphasis", "switch_layout"],
                    "description": "The type of layout action"
                },
                "widget_order": {
                    "type": "array", 
                    "items": {"type": "string"},
                    "description": "Order of widgets for reorder_widgets action"
                },
                "widget": {
                    "type": "string", 
                    "description": "Widget type for toggle (e.g., 'KpiCard', 'MetricChart', 'NewsTimeline')"
                },
                "visible": {
                    "type": "boolean",
                    "description": "Whether widget should be visible (for toggle_widget)"
                },
                "emphasis": {
                    "type": "string", 
                    "enum": ["balanced", "focus_chart", "focus_table", "focus_news"],
                    "description": "Emphasis mode for set_emphasis action"
                },
                "rationale": {"type": "string"}
            },
            "required": ["action", "rationale"]
        }
    },
    {
        "name": "modify_data",
        "description": """
        Refine the current analysis by changing data parameters.
        Use this when the user:
        - Adds tickers to comparison (e.g., "add AMD", "include INTC")
        - Removes tickers (e.g., "remove AMD from comparison")
        - Changes timeframe (e.g., "show last year", "change to 6 months")
        - Changes metric (e.g., "show gross margin instead", "switch to operating margin")
        
        Examples: "Add AMD to the comparison", "Show me the last 6 months", "Compare net margin instead"
        """,
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add_ticker", "remove_ticker", "change_timeframe", "change_metric"],
                    "description": "The type of data modification"
                },
                "ticker": {"type": "string", "description": "Ticker symbol for add/remove"},
                "timeframe": {"type": "string", "description": "New timeframe (1M, 3M, 6M, 1Y)"},
                "metric": {"type": "string", "description": "New metric name"},
                "rationale": {"type": "string"}
            },
            "required": ["action", "rationale"]
        }
    },
    {
        "name": "switch_component",
        "description": """
        Change how data is visualized without changing the data itself.
        Use this when the user:
        - Wants to swap component types (e.g., "show as table", "make it a chart")
        - Targets a specific component for transformation
        
        Examples: "Show that as a table", "Convert the chart to a data grid", "Make it a bar chart"
        """,
        "input_schema": {
            "type": "object",
            "properties": {
                "target_component": {
                    "type": "string", 
                    "description": "Component type to transform (e.g., 'MetricChart', 'DataTable')"
                },
                "new_type": {
                    "type": "string",
                    "description": "New component type to transform into"
                },
                "rationale": {"type": "string"}
            },
            "required": ["target_component", "new_type", "rationale"]
        }
    },
    {
        "name": "follow_up_question",
        "description": """
        Continue the conversation with a question about the current data.
        Use this when the user:
        - Asks for more details about something visible (e.g., "why is this high?")
        - Requests explanation or summary (e.g., "explain this", "summarize")
        - Asks clarifying questions about the current analysis
        - Wants to understand a specific data point
        
        Examples: "Why is the gross margin so high?", "What's driving this trend?", "Explain that spike"
        """,
        "input_schema": {
            "type": "object",
            "properties": {
                "question_type": {
                    "type": "string",
                    "enum": ["explain", "summarize", "compare", "predict", "detail"],
                    "description": "Type of follow-up question"
                },
                "target_element": {
                    "type": "string", 
                    "description": "What the question is about (metric, component, data point)"
                },
                "rationale": {"type": "string"}
            },
            "required": ["question_type", "rationale"]
        }
    },
]


class CommandRouter:
    """
    LLM-driven command router for conversational dashboard control.
    
    Class: CommandRouter
    Called from: dashboard routes
    Invokes: Anthropic API with tool calling
    Why: Unified intent classification for all user inputs.
    """
    
    SYSTEM_PROMPT = """You are an intent classifier for a financial analytics dashboard.

Your job is to understand what the user wants to do and call the appropriate tool.
The user is currently viewing a dashboard with specific data and components.

CURRENT DASHBOARD CONTEXT:
{context}

Based on the user's query, determine their intent and call the appropriate tool.

RULES:
1. If the user is CLEARLY asking for a new analysis topic (different ticker, different skill), use new_analysis
2. If the user wants to change LAYOUT only (position, visibility, size, emphasis), use modify_layout
3. If the user wants to change DATA parameters (add ticker, change timeframe), use modify_data
4. If the user wants to SWAP visualization types, use switch_component
5. If the user is asking a QUESTION about the current data, use follow_up_question

IMPORTANT DISTINCTIONS:
- "Add AMD" when analyzing NVDA = modify_data (adding to current analysis)
- "Analyze AMD" when analyzing NVDA = new_analysis (completely new topic)
- "Show margins as a table" = switch_component
- "Put the table on top" = modify_layout
- "Why is this high?" = follow_up_question

Always provide a rationale explaining your reasoning.
"""

    def __init__(self):
        """
        Initialize the router.
        
        Method: __init__
        Called from: get_command_router()
        Why: Sets up SDK wrapper and conversation store references.
        """
        self.conversation_store = get_conversation_store()

    async def classify_intent(
        self,
        query: str,
        dashboard_id: Optional[str] = None,
        current_context: Optional[Dict[str, Any]] = None,
        recent_messages: Optional[List[Dict[str, str]]] = None,
    ) -> IntentClassification:
        """
        Classify user intent using LLM tool calling.
        
        Method: classify_intent
        Called from: handle_query route
        Invokes: Anthropic Messages API with tool calling
        Why: Determines user intent without hardcoded keywords.
        
        Args:
            query: User's text input
            dashboard_id: Current dashboard ID (if any)
            current_context: Current dashboard context (skill, tickers, data)
            recent_messages: Optional recent message history for context
            
        Returns:
            IntentClassification with intent type and action parameters
        """
        # Build context string for the system prompt
        context_str = self._build_context_string(dashboard_id, current_context)
        system_prompt = self.SYSTEM_PROMPT.format(context=context_str)
        
        # Use SDK wrapper for the API call
        sdk = get_sdk_wrapper()
        
        try:
            messages = recent_messages or [{"role": "user", "content": query}]
            # Initialize with intent classification tools
            await sdk.initialize(
                system_prompt=system_prompt,
                tools=INTENT_TOOLS,
            )
            
            # Query Claude to classify intent
            response = await sdk.query(
                prompt=query,
                max_tokens=512,
                temperature=0.3,  # Low temperature for consistent classification
                messages=messages,
                tool_choice={"type": "any", "disable_parallel_tool_use": True},
            )
            
            if response.error:
                logger.warning("Intent classification failed: %s", response.error)
                return IntentClassification(intent="unknown", rationale=response.error)
            
            # Parse tool call response
            return self._parse_tool_response(response)
            
        except Exception as e:
            logger.exception("Intent classification error: %s", e)
            return IntentClassification(
                intent="unknown",
                rationale=f"Classification failed: {str(e)}"
            )

    def _build_context_string(
        self,
        dashboard_id: Optional[str],
        context: Optional[Dict[str, Any]],
    ) -> str:
        """
        Build context string for the system prompt.
        
        Method: _build_context_string
        Called from: classify_intent
        Why: Provides LLM with dashboard state for informed decisions.
        """
        if not dashboard_id:
            return "No dashboard is currently active. This is a new session."
        
        if not context:
            return f"Dashboard {dashboard_id} is active but no context available."
        
        parts = [f"Dashboard ID: {dashboard_id}"]
        
        if skill := context.get("skill_id"):
            parts.append(f"Current skill: {skill}")
        if tickers := context.get("tickers"):
            parts.append(f"Currently analyzing: {', '.join(tickers)}")
        if metric := context.get("metric"):
            parts.append(f"Current metric: {metric}")
        if time_range := context.get("time_range"):
            parts.append(f"Time range: {time_range}")
        if components := context.get("visible_components"):
            parts.append(f"Visible components: {', '.join(components)}")
        
        return "\n".join(parts)

    def _parse_tool_response(self, response) -> IntentClassification:
        """
        Parse Claude's tool call into IntentClassification.
        
        Method: _parse_tool_response
        Called from: classify_intent
        Why: Converts SDK response to typed classification with confidence scoring.
        """
        if not response.tool_calls:
            # No tool call - try to infer from text
            logger.warning("No tool call in response, defaulting to unknown")
            return IntentClassification(
                intent="unknown",
                rationale="No tool call in response",
                confidence=0.0,
            )
        
        tool_call = response.tool_calls[0]
        # SDKToolCall is a dataclass, not a dict
        tool_name = tool_call.name
        params = tool_call.input
        
        # Map tool names to intent types
        intent_map = {
            "new_analysis": "new_analysis",
            "modify_layout": "modify_layout",
            "modify_data": "modify_data",
            "switch_component": "switch_component",
            "follow_up_question": "follow_up",
        }
        
        intent = intent_map.get(tool_name, "unknown")
        
        # Calculate confidence based on rationale quality and tool match
        confidence = self._calculate_confidence(
            tool_name=tool_name,
            params=params,
            intent=intent,
        )
        
        # Apply clarification fallback if confidence is too low
        if confidence < CONFIDENCE_THRESHOLD and intent != "unknown":
            logger.info(
                "[ROUTER] Low confidence (%.2f) for intent '%s', switching to clarification",
                confidence, intent
            )
            return IntentClassification(
                intent="clarification",
                action_name=None,
                action_params={
                    "original_intent": intent,
                    "original_params": params,
                },
                should_continue=True,
                rationale=f"Low confidence ({confidence:.2f}) - asking for clarification",
                confidence=confidence,
            )
        
        return IntentClassification(
            intent=intent,
            action_name=params.get("action"),
            action_params=params,
            should_continue=intent != "new_analysis",
            rationale=params.get("rationale", ""),
            confidence=confidence,
        )
    
    def _calculate_confidence(
        self,
        tool_name: str,
        params: Dict[str, Any],
        intent: str,
    ) -> float:
        """
        Calculate confidence score for an intent classification.
        
        Method: _calculate_confidence
        Called from: _parse_tool_response
        Why: Enables clarification fallback for ambiguous queries.
        
        Heuristics:
        - Good rationale: +0.2
        - Valid tool: +0.3
        - Required params present: +0.2 per param
        - Intent != unknown: +0.2
        """
        confidence = 0.0
        
        # Valid tool call adds base confidence
        if tool_name in ("new_analysis", "modify_layout", "modify_data", "switch_component", "follow_up_question"):
            confidence += 0.3
        
        # Intent resolved adds confidence
        if intent != "unknown":
            confidence += 0.2
        
        # Rationale present and substantive
        rationale = params.get("rationale", "")
        if rationale and len(rationale) > 10:
            confidence += 0.2
        
        # Check for required parameters based on intent
        if tool_name == "new_analysis" and params.get("query"):
            confidence += 0.2
        elif tool_name == "modify_layout" and params.get("action"):
            confidence += 0.2
        elif tool_name == "modify_data" and params.get("action"):
            confidence += 0.2
            if params.get("ticker") or params.get("timeframe"):
                confidence += 0.1
        elif tool_name == "switch_component" and params.get("new_type"):
            confidence += 0.2
        elif tool_name == "follow_up_question" and params.get("question_type"):
            confidence += 0.2
        
        return min(1.0, confidence)


# Singleton instance
_router: Optional[CommandRouter] = None


def get_command_router() -> CommandRouter:
    """
    Get or create the singleton CommandRouter instance.
    
    Function: get_command_router
    Called from: dashboard routes
    Why: Provides single router instance for the application.
    """
    global _router
    if _router is None:
        _router = CommandRouter()
    return _router
