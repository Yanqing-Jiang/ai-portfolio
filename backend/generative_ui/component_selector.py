# --- Component Selector Function/Class Map ---
# Class: ComponentSelector
#   Role: LLM-powered component selection for A2UI dashboards.
#   Called from: backend.generative_ui.runtime.A2UIRuntime.stream_dashboard
#   Invokes: A2UISDKWrapper.query, ComponentValidator.validate_selection
#   Why: Enables LLM to dynamically select and configure dashboard widgets.
# Function: build_component_selection_tool
#   Role: Build Anthropic tool schema with data path constraints.
#   Called from: ComponentSelector.select_components
#   Invokes: n/a
#   Why: Provides structured tool schema for LLM component selection.
# --- End Component Selector Function/Class Map ---
"""
LLM-powered component selection for A2UI dashboards.

This module enables the LLM to dynamically select which widgets to display
and how to bind them to data paths, based on the user's query and skill context.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .skills import A2UISkillMeta

logger = logging.getLogger(__name__)


class WidgetSelection(BaseModel):
    """
    LLM-selected widget configuration.

    Model: WidgetSelection - represents a single widget selection by the LLM.
    Called from: ComponentSelector.select_components
    Why: Structured representation of LLM widget choices with data bindings.
    """

    widget_type: str = Field(
        ...,
        description="Component type from catalog (e.g., 'KpiCard', 'MetricChart')"
    )
    widget_id: str = Field(
        ...,
        description="Unique ID for this widget instance (e.g., 'kpi_revenue')"
    )
    data_bindings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Map of property names to data paths or literal values"
    )
    priority: int = Field(
        default=50,
        description="Display priority (0=top, 100=bottom)"
    )


class WidgetTypeSelection(BaseModel):
    """
    LLM-selected widget types (without IDs/bindings - those come from layout.json).

    Model: WidgetTypeSelection - LLM decides WHICH types to show, layout.json provides HOW.
    Called from: ComponentSelector.stream_widget_types
    Why: Separates LLM reasoning (what to show) from hardcoded config (IDs, bindings).
    """

    widget_types: List[str] = Field(
        ...,
        description="Widget types to display (e.g., ['PriceChart', 'KpiCard', 'NewsTimeline'])"
    )
    rationale: str = Field(
        ...,
        description="Brief explanation of why these widgets were selected for this query"
    )


class DashboardLayout(BaseModel):
    """
    LLM-generated dashboard layout specification.
    
    Model: DashboardLayout - complete widget selection for a dashboard.
    Called from: ComponentSelector.select_components
    Why: Container for all widget selections with layout metadata.
    """
    
    widgets: List[WidgetSelection] = Field(
        ...,
        description="Ordered list of widgets to display"
    )
    emphasis: Optional[str] = Field(
        default="balanced",
        description="Layout emphasis: focus_chart, focus_table, focus_news, or balanced"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="Brief explanation of why this layout was chosen"
    )


def build_component_selection_tool(skill: A2UISkillMeta) -> dict:
    """
    Build Anthropic tool schema with data path constraints.
    
    Function: build_component_selection_tool - creates tool schema for LLM.
    Called from: ComponentSelector.select_components
    Invokes: skill.all_data_paths, skill.widget_bindings
    Why: Constrains LLM to valid widget types and data paths.
    """
    # Get all valid data paths for enum constraint
    valid_paths = skill.all_data_paths
    
    return {
        "name": "select_dashboard_components",
        "description": f"""Select and configure dashboard components for the {skill.name} skill.

You MUST use only the data paths listed below for bindings. Invalid paths will cause errors.

Available Widgets: {', '.join(skill.widgets)}

Valid Data Paths:
{json.dumps(valid_paths, indent=2)}

Widget Binding Rules:
{json.dumps(skill.widget_bindings, indent=2)}

Guidelines:
- Include 3-6 widgets for a balanced dashboard
- Always include at least one KpiCard for key metrics
- Use MetricChart or PriceChart for trends
- Use DataTable for detailed data
- Use ExplainMovePanel for AI insights
- Lower priority numbers appear first (0 = top)
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "widgets": {
                    "type": "array",
                    "description": "List of widgets to display",
                    "items": {
                        "type": "object",
                        "properties": {
                            "widget_type": {
                                "type": "string",
                                "enum": skill.widgets,
                                "description": "Component type from skill's widget list"
                            },
                            "widget_id": {
                                "type": "string",
                                "description": "Unique widget ID (lowercase_snake_case)"
                            },
                            "data_bindings": {
                                "type": "object",
                                "description": "Property-to-data-path mappings. Use {path: '/data/...'} for bound values or {literalString: '...'} for literals"
                            },
                            "priority": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                                "description": "Display order (0=first, 100=last)"
                            }
                        },
                        "required": ["widget_type", "widget_id"]
                    },
                    "minItems": 2,
                    "maxItems": 8
                },
                "emphasis": {
                    "type": "string",
                    "enum": ["focus_chart", "focus_table", "focus_news", "balanced"],
                    "description": "Layout emphasis mode"
                },
                "rationale": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Why this layout answers the query"
                }
            },
            "required": ["widgets"]
        }
    }


class ComponentSelector:
    """
    LLM-powered component selection for A2UI dashboards.
    
    Class: ComponentSelector - orchestrates LLM component selection.
    Called from: backend.generative_ui.runtime.A2UIRuntime.stream_dashboard
    Invokes: A2UISDKWrapper.query, build_component_selection_tool
    Why: Dynamically selects widgets based on query context.
    """
    
    def __init__(self):
        """Initialize the component selector."""
        self._sdk_wrapper = None
    
    async def _get_sdk_wrapper(self):
        """Lazy-load SDK wrapper to avoid circular imports."""
        if self._sdk_wrapper is None:
            from .sdk_wrapper import get_sdk_wrapper
            self._sdk_wrapper = get_sdk_wrapper()
            if not self._sdk_wrapper.is_initialized:
                await self._sdk_wrapper.initialize()
        return self._sdk_wrapper
    
    async def select_components(
        self,
        skill: A2UISkillMeta,
        question: str,
        context: Dict[str, Any],
    ) -> Optional[DashboardLayout]:
        """
        Use LLM to select dashboard components.
        
        Method: select_components - LLM-powered widget selection.
        Called from: backend.generative_ui.runtime.A2UIRuntime.stream_dashboard
        Invokes: A2UISDKWrapper.query, build_component_selection_tool
        Why: Generates contextual widget selection based on user query.
        
        Args:
            skill: The selected A2UI skill
            question: User's original question
            context: Render context with tickers, metrics, etc.
            
        Returns:
            DashboardLayout with selected widgets, or None on failure
        """
        try:
            wrapper = await self._get_sdk_wrapper()
            
            # Build context summary
            tickers = context.get("tickers", [])
            primary_ticker = context.get("primary_ticker", tickers[0] if tickers else "")
            metric = context.get("metric", "")
            
            prompt = f"""Select dashboard widgets to answer this question:

Question: {question}
Primary Ticker: {primary_ticker}
All Tickers: {', '.join(tickers)}
Metric Focus: {metric}
Skill: {skill.name}

Available Widgets: {', '.join(skill.widgets)}

Valid Data Paths for Bindings:
{json.dumps(skill.all_data_paths, indent=2)}

Return a JSON object with:
- widgets: array of widget objects with widget_type, widget_id, data_bindings, priority
- emphasis: one of focus_chart, focus_table, focus_news, balanced
- rationale: brief explanation

Example widget binding:
{{
  "widget_type": "KpiCard",
  "widget_id": "kpi_revenue", 
  "data_bindings": {{
    "value": {{"path": "/data/kpis/latest_revenue"}},
    "label": {{"literalString": "Revenue"}},
    "unit": {{"literalString": "$"}}
  }},
  "priority": 0
}}

Return ONLY valid JSON. No markdown, no explanation."""

            response = await wrapper.query(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.3,
            )
            
            if response.error or not response.content:
                logger.warning("LLM component selection failed: %s", response.error)
                return None
            
            # Parse LLM response
            layout = self._parse_response(response.content, skill)
            if layout:
                logger.info(
                    "[COMPONENT_SELECTOR] LLM selected %d widgets: %s",
                    len(layout.widgets),
                    [w.widget_type for w in layout.widgets]
                )
            return layout
            
        except Exception as e:
            logger.error("Component selection error: %s", e)
            return None
    
    def _parse_response(
        self, 
        content: str, 
        skill: A2UISkillMeta
    ) -> Optional[DashboardLayout]:
        """
        Parse LLM response into DashboardLayout.
        
        Method: _parse_response - extracts structured layout from LLM output.
        Called from: ComponentSelector.select_components
        Invokes: json.loads, DashboardLayout.model_validate
        Why: Normalizes LLM output into validated Pydantic model.
        """
        try:
            # Clean response - find JSON object
            content = content.strip()
            
            # Try to find JSON in response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx < 0 or end_idx <= start_idx:
                logger.warning("No JSON object found in LLM response")
                return None
            
            json_str = content[start_idx:end_idx]
            data = json.loads(json_str)
            
            # Validate widgets exist
            if "widgets" not in data or not data["widgets"]:
                logger.warning("No widgets in LLM response")
                return None
            
            # Filter to valid widget types only
            valid_widgets = []
            for w in data["widgets"]:
                if w.get("widget_type") in skill.widgets:
                    valid_widgets.append(WidgetSelection(
                        widget_type=w["widget_type"],
                        widget_id=w.get("widget_id", f"widget_{len(valid_widgets)}"),
                        data_bindings=w.get("data_bindings", {}),
                        priority=w.get("priority", 50),
                    ))
                else:
                    logger.warning(
                        "Ignoring invalid widget type: %s", 
                        w.get("widget_type")
                    )
            
            if not valid_widgets:
                logger.warning("No valid widgets after filtering")
                return None
            
            return DashboardLayout(
                widgets=valid_widgets,
                emphasis=data.get("emphasis", "balanced"),
                rationale=data.get("rationale"),
            )
            
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse LLM response as JSON: %s", e)
            return None
        except Exception as e:
            logger.warning("Error parsing component selection: %s", e)
            return None

    async def stream_components(
        self,
        skill: A2UISkillMeta,
        question: str,
        context: Dict[str, Any],
    ):
        """
        Stream widget selections as they're generated by the LLM.
        
        Method: stream_components - progressive widget generation.
        Called from: A2UIRuntime._stream_component_selection (when streaming enabled)
        Invokes: A2UISDKWrapper.stream_with_tools
        Why: Enables progressive rendering for faster time-to-first-paint.
        
        Args:
            skill: The selected A2UI skill
            question: User's original question
            context: Render context with tickers, metrics, etc.
            
        Yields:
            WidgetSelection objects as they complete
        """
        try:
            wrapper = await self._get_sdk_wrapper()
            
            # Build context summary
            tickers = context.get("tickers", [])
            primary_ticker = context.get("primary_ticker", tickers[0] if tickers else "")
            metric = context.get("metric", "")
            
            prompt = f"""Select dashboard widgets to answer this question:

Question: {question}
Primary Ticker: {primary_ticker}
All Tickers: {', '.join(tickers)}
Metric Focus: {metric}
Skill: {skill.name}

Available Widgets: {', '.join(skill.widgets)}

Valid Data Paths for Bindings:
{json.dumps(skill.all_data_paths, indent=2)}

Return a JSON object with:
- widgets: array of widget objects with widget_type, widget_id, data_bindings, priority
- emphasis: one of focus_chart, focus_table, focus_news, balanced
- rationale: brief explanation

Example widget binding:
{{
  "widget_type": "KpiCard",
  "widget_id": "kpi_revenue", 
  "data_bindings": {{
    "value": {{"path": "/data/kpis/latest_revenue"}},
    "label": {{"literalString": "Revenue"}},
    "unit": {{"literalString": "$"}}
  }},
  "priority": 0
}}

Return ONLY valid JSON. No markdown, no explanation."""

            tool_schema = build_component_selection_tool(skill)
            
            # Accumulate partial JSON
            json_buffer = ""
            widgets_emitted: set = set()
            
            async for event in wrapper.stream_with_tools(
                prompt=prompt,
                tools=[tool_schema],
                max_tokens=1500,
                temperature=0.3,
            ):
                if event.get("type") == "partial_json":
                    json_buffer += event.get("content", "")
                    
                    # Try to extract complete widgets from buffer
                    for widget in self._extract_complete_widgets(json_buffer, skill):
                        if widget.widget_id not in widgets_emitted:
                            widgets_emitted.add(widget.widget_id)
                            logger.debug(
                                "[STREAM] Widget extracted: %s (%s)",
                                widget.widget_type, widget.widget_id
                            )
                            yield widget
                
                elif event.get("type") == "done":
                    # Final pass - emit any remaining widgets from complete JSON
                    for widget in self._parse_remaining_widgets(json_buffer, skill):
                        if widget.widget_id not in widgets_emitted:
                            widgets_emitted.add(widget.widget_id)
                            logger.debug(
                                "[STREAM] Final widget: %s (%s)",
                                widget.widget_type, widget.widget_id
                            )
                            yield widget
                    break
                
                elif event.get("type") == "error":
                    logger.warning(
                        "[STREAM] Streaming error: %s",
                        event.get("error")
                    )
                    break
            
            logger.info(
                "[STREAM] Completed streaming %d widgets",
                len(widgets_emitted)
            )
            
        except Exception as e:
            logger.error("Stream components error: %s", e)
            # Don't yield anything on error - caller should fallback

    def _extract_complete_widgets(
        self, 
        json_buffer: str, 
        skill: A2UISkillMeta
    ) -> List[WidgetSelection]:
        """
        Extract any complete widget objects from partial JSON buffer.
        
        Method: _extract_complete_widgets - parses incomplete JSON for widgets.
        Called from: stream_components
        Invokes: _brace_balanced_extract, fallback to regex
        Why: Enables progressive widget emission before full JSON is complete.
        
        Uses a brace-balanced parser for robustness, with regex as fallback.
        """
        widgets = []
        
        # Primary: brace-balanced extraction (handles nested objects)
        try:
            widgets = self._brace_balanced_extract(json_buffer, skill)
            if widgets:
                return widgets
        except Exception as e:
            logger.debug("[STREAM] Brace-balanced extraction failed: %s, trying regex", e)
        
        # Fallback: regex extraction for simpler cases
        return self._regex_extract_widgets(json_buffer, skill)
    
    def _brace_balanced_extract(
        self, 
        json_buffer: str, 
        skill: A2UISkillMeta
    ) -> List[WidgetSelection]:
        """
        Extract complete widget objects using brace-balanced parsing.
        
        Method: _brace_balanced_extract - robust JSON object extraction.
        Called from: _extract_complete_widgets
        Invokes: json.loads
        Why: More robust than regex for nested structures and special characters.
        """
        widgets = []
        i = 0
        n = len(json_buffer)
        
        while i < n:
            # Find start of potential widget object
            start = json_buffer.find('{"widget_type"', i)
            if start == -1:
                # Also try with spaces
                start = json_buffer.find('{ "widget_type"', i)
            if start == -1:
                break
            
            # Track braces to find complete object
            brace_count = 0
            in_string = False
            escape_next = False
            end = -1
            
            for j in range(start, n):
                char = json_buffer[j]
                
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"':
                    in_string = not in_string
                    continue
                
                if in_string:
                    continue
                
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = j + 1
                        break
            
            if end == -1:
                # Incomplete object, stop processing
                break
            
            # Try to parse the complete object
            obj_str = json_buffer[start:end]
            try:
                obj = json.loads(obj_str)
                widget_type = obj.get("widget_type")
                if widget_type and widget_type in skill.widgets:
                    widgets.append(WidgetSelection(
                        widget_type=widget_type,
                        widget_id=obj.get("widget_id", f"widget_{len(widgets)}"),
                        data_bindings=obj.get("data_bindings", {}),
                        priority=obj.get("priority", 50),
                    ))
            except json.JSONDecodeError as e:
                logger.debug("[STREAM] JSON parse failed for object: %s", e)
            
            i = end
        
        return widgets
    
    def _regex_extract_widgets(
        self, 
        json_buffer: str, 
        skill: A2UISkillMeta
    ) -> List[WidgetSelection]:
        """
        Extract widgets using regex (fallback method).
        
        Method: _regex_extract_widgets - fallback regex parsing.
        Called from: _extract_complete_widgets
        Why: Simpler extraction for cases where brace-balanced fails.
        
        Note: This is less robust for nested objects but useful as fallback.
        """
        import re
        widgets = []
        
        # Pattern to match complete widget objects (simple cases only)
        pattern = r'\{[^{}]*"widget_type"\s*:\s*"([^"]+)"[^{}]*\}'
        
        for match in re.finditer(pattern, json_buffer):
            try:
                obj_str = match.group()
                obj = json.loads(obj_str)
                
                widget_type = obj.get("widget_type")
                if widget_type and widget_type in skill.widgets:
                    widgets.append(WidgetSelection(
                        widget_type=widget_type,
                        widget_id=obj.get("widget_id", f"widget_{len(widgets)}"),
                        data_bindings=obj.get("data_bindings", {}),
                        priority=obj.get("priority", 50),
                    ))
            except json.JSONDecodeError:
                # Incomplete or malformed object, skip
                continue
        
        return widgets

    def _parse_remaining_widgets(
        self, 
        json_buffer: str, 
        skill: A2UISkillMeta
    ) -> List[WidgetSelection]:
        """
        Parse remaining widgets from complete JSON buffer.
        
        Method: _parse_remaining_widgets - final parsing of complete response.
        Called from: stream_components
        Invokes: _parse_response
        Why: Catches any widgets that streaming extraction might have missed.
        """
        # Try to parse using the standard parser
        layout = self._parse_response(json_buffer, skill)
        if layout:
            return layout.widgets
        return []

    async def select_widget_types(
        self,
        skill: A2UISkillMeta,
        question: str,
        context: Dict[str, Any],
    ) -> Optional[WidgetTypeSelection]:
        """
        LLM selects widget TYPES only. IDs and bindings come from layout.json.

        Method: select_widget_types - simplified LLM selection (types + rationale only).
        Called from: A2UIRuntime._stream_component_selection
        Invokes: A2UISDKWrapper.query
        Why: LLM decides WHAT to show, layout.json provides HOW (IDs, bindings).
        """
        try:
            wrapper = await self._get_sdk_wrapper()

            tickers = context.get("tickers", [])
            primary_ticker = context.get("primary_ticker", tickers[0] if tickers else "")
            metric = context.get("metric", "")

            prompt = f"""Select which widget types to display for this question.

Question: {question}
Primary Ticker: {primary_ticker}
All Tickers: {', '.join(tickers)}
Metric Focus: {metric}
Skill: {skill.name}

Available Widget Types: {', '.join(skill.widgets)}

Return a JSON object with:
- widget_types: array of widget type names to display (from Available Widget Types)
- rationale: brief explanation of why you selected these widgets for this query

Guidelines:
- Select 2-5 widget types based on what's most relevant to the question
- PriceChart: for stock price visualization
- KpiCard: for key financial metrics (revenue, margins, etc.)
- NewsTimeline: when news/events are relevant to the question
- ExplainMovePanel: for AI-generated analysis and explanations
- DataTable: for detailed tabular data

Return ONLY valid JSON. No markdown, no explanation outside the rationale field.

Example response:
{{
  "widget_types": ["PriceChart", "KpiCard", "ExplainMovePanel"],
  "rationale": "Selected PriceChart to show NVDA price movement, KpiCard for key financials, and ExplainMovePanel for AI analysis of the drop."
}}"""

            response = await wrapper.query(
                prompt=prompt,
                max_tokens=500,
                temperature=0.3,
            )

            # Handle SDKResponse object (has .content attribute, not .get() method)
            if response.error:
                logger.warning("Widget type selection API error: %s", response.error)
                return None

            content = response.content
            if not content:
                return None

            # Extract JSON from response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1

            if start_idx < 0 or end_idx <= start_idx:
                logger.warning("No JSON object found in widget type selection response")
                return None

            json_str = content[start_idx:end_idx]
            data = json.loads(json_str)

            # Validate widget types
            valid_types = [t for t in data.get("widget_types", []) if t in skill.widgets]
            if not valid_types:
                logger.warning("No valid widget types in LLM response")
                return None

            return WidgetTypeSelection(
                widget_types=valid_types,
                rationale=data.get("rationale", ""),
            )

        except Exception as e:
            logger.error("Widget type selection error: %s", e)
            return None


def get_components_by_types(
    skill: A2UISkillMeta,
    selected_types: List[str],
) -> List[WidgetSelection]:
    """
    Map LLM-selected widget types to hardcoded components from layout.json.

    Function: get_components_by_types - converts types to full widget specs.
    Called from: A2UIRuntime._stream_component_selection
    Invokes: skill.layout_config["component_tree"]
    Why: Ensures widget IDs and data bindings are consistent (from layout.json).
    """
    if not skill.layout_config:
        logger.warning("No layout_config for skill %s", skill.skill_id)
        return []

    component_tree = skill.layout_config.get("component_tree", {})
    widgets = []

    # Find all components matching the selected types
    for comp_id, comp_def in component_tree.items():
        comp_type = comp_def.get("type")
        if comp_type in selected_types:
            # Build data_bindings from props
            props = comp_def.get("props", {})
            data_bindings = {}
            for prop_name, prop_value in props.items():
                if isinstance(prop_value, dict):
                    data_bindings[prop_name] = prop_value

            widgets.append(WidgetSelection(
                widget_type=comp_type,
                widget_id=comp_id,
                data_bindings=data_bindings,
                priority=len(widgets) * 10,  # Order by appearance in component_tree
            ))

    logger.info(
        "[SELECTOR] Mapped %d types to %d components: %s",
        len(selected_types),
        len(widgets),
        [w.widget_id for w in widgets]
    )
    return widgets


# Singleton instance
_selector: Optional[ComponentSelector] = None


def get_component_selector() -> ComponentSelector:
    """Get the component selector singleton."""
    global _selector
    if _selector is None:
        _selector = ComponentSelector()
    return _selector


__all__ = [
    "WidgetSelection",
    "WidgetTypeSelection",
    "DashboardLayout",
    "ComponentSelector",
    "get_component_selector",
    "get_components_by_types",
    "build_component_selection_tool",
]
