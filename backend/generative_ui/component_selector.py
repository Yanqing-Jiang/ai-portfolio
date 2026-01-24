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


def build_llm_component_tool(skill: A2UISkillMeta) -> dict:
    """
    Build Anthropic tool schema for generate_dashboard_components.

    Function: build_llm_component_tool - creates tool for full LLM component generation.
    Called from: LLMComponentGenerator.generate_components
    Invokes: skill.widgets, skill.widget_bindings, skill.all_data_paths
    Why: Enables LLM to generate complete widget specs with IDs and bindings.
    """
    # Build widget binding documentation for the prompt
    binding_docs = []
    for widget_type, rules in skill.widget_bindings.items():
        if widget_type not in skill.widgets:
            continue
        doc = f"\n{widget_type}:"
        for key, value in rules.items():
            if isinstance(value, list):
                doc += f"\n  - {key}: {value}"
            elif isinstance(value, str):
                doc += f"\n  - {key}: {value}"
        binding_docs.append(doc)

    return {
        "name": "generate_dashboard_components",
        "description": f"""Generate dashboard components for {skill.name}.

You MUST create 3-6 widgets with:
1. Unique widget_id in snake_case (e.g., 'kpi_revenue', 'chart_comparison')
2. Valid widget_type from: {', '.join(skill.widgets)}
3. Correct data_bindings using paths from the skill schema

Widget Binding Rules:
{''.join(binding_docs)}

For data bindings, use:
- {{"path": "/data/..."}} for data-bound values
- {{"literalString": "..."}} for static text
- {{"literalNumber": ...}} for static numbers

Include follow_up_actions for continuous analysis opportunities.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "components": {
                    "type": "array",
                    "description": "List of widget components to render",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Unique widget ID in snake_case (e.g., 'kpi_revenue')"
                            },
                            "type": {
                                "type": "string",
                                "enum": list(set(skill.widgets)),  # Dedupe widget types
                                "description": "Widget type from skill's available widgets"
                            },
                            "bindings": {
                                "type": "object",
                                "description": "Property-to-data-path mappings"
                            },
                            "priority": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                                "description": "Display priority (0=top, 100=bottom)"
                            }
                        },
                        "required": ["id", "type", "bindings"]
                    },
                    "minItems": 2,
                    "maxItems": 8
                },
                "rationale": {
                    "type": "string",
                    "description": "Brief explanation of widget selection"
                },
                "follow_up_actions": {
                    "type": "array",
                    "description": "Suggested follow-up analyses",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "action": {
                                "type": "string",
                                "enum": ["new_tab", "swap", "drill_down"]
                            },
                            "query": {"type": "string"}
                        },
                        "required": ["label", "action", "query"]
                    }
                }
            },
            "required": ["components"]
        }
    }


def validate_llm_components(
    components: List[dict],
    skill: A2UISkillMeta
) -> tuple[List[WidgetSelection], List[str]]:
    """
    Validate LLM-generated components against skill schema.

    Function: validate_llm_components - enforces schema compliance.
    Called from: LLMComponentGenerator._parse_and_validate
    Invokes: n/a
    Why: Catches invalid components before they reach the frontend.

    Returns:
        (valid_widgets, errors) - tuple of valid selections and error messages
    """
    valid: List[WidgetSelection] = []
    errors: List[str] = []
    seen_ids: set = set()

    # Get valid widget types (deduplicated)
    valid_types = set(skill.widgets)

    # Get valid data paths
    valid_paths: set = set()
    for path in skill.data_paths.values():
        valid_paths.add(path)
    for base_path, schema in skill.data_schema.items():
        valid_paths.add(base_path)
        if isinstance(schema, dict) and "properties" in schema:
            for prop in schema["properties"]:
                valid_paths.add(f"{base_path}/{prop}")
    for widget_rules in skill.widget_bindings.values():
        if isinstance(widget_rules, dict):
            for key, value in widget_rules.items():
                if isinstance(value, list):
                    valid_paths.update(value)
                elif isinstance(value, str) and value.startswith("/"):
                    valid_paths.add(value)

    for comp in components:
        comp_type = comp.get("type")
        comp_id = comp.get("id")
        bindings = comp.get("bindings", {})
        priority = comp.get("priority", len(valid) * 10)

        # Check type is valid
        if comp_type not in valid_types:
            errors.append(f"Invalid widget type: {comp_type}. Valid: {valid_types}")
            continue

        # Check ID exists and is unique
        if not comp_id:
            errors.append(f"Missing widget ID for {comp_type}")
            continue

        if comp_id in seen_ids:
            errors.append(f"Duplicate widget ID: {comp_id}")
            continue
        seen_ids.add(comp_id)

        # Check ID format (snake_case)
        import re
        if not re.match(r'^[a-z][a-z0-9_]*$', comp_id):
            errors.append(f"Invalid ID format '{comp_id}'. Must be lowercase snake_case.")
            continue

        # Validate bindings have valid paths
        binding_errors = []
        for prop_name, binding in bindings.items():
            if isinstance(binding, dict) and "path" in binding:
                path = binding["path"]
                # Check if path is valid (starts with /data and exists in schema)
                if not path.startswith("/data"):
                    binding_errors.append(f"{comp_type}.{prop_name}: path must start with /data")
                elif path not in valid_paths:
                    # Allow nested paths even if not explicitly in schema
                    path_valid = any(
                        path.startswith(valid + "/") or path == valid
                        for valid in valid_paths
                    )
                    if not path_valid:
                        # Log warning but don't reject - schema might be incomplete
                        logger.debug(
                            "[VALIDATOR] Path %s not in schema for %s.%s",
                            path, comp_type, prop_name
                        )

        if binding_errors:
            errors.extend(binding_errors)
            continue

        # Component is valid
        valid.append(WidgetSelection(
            widget_type=comp_type,
            widget_id=comp_id,
            data_bindings=bindings,
            priority=priority,
        ))

    return valid, errors


class LLMComponentGenerator:
    """
    LLM-powered component generator for A2UI dashboards.

    Class: LLMComponentGenerator - generates complete widget specs via LLM tool calls.
    Called from: backend.generative_ui.runtime.A2UIRuntime._stream_component_selection
    Invokes: A2UISDKWrapper.query_with_tools, validate_llm_components
    Why: Replaces static component_tree with dynamic LLM-generated layouts.
    """

    def __init__(self):
        """Initialize the component generator."""
        self._sdk_wrapper = None

    async def _get_sdk_wrapper(self):
        """Lazy-load SDK wrapper to avoid circular imports."""
        if self._sdk_wrapper is None:
            from .sdk_wrapper import get_sdk_wrapper
            self._sdk_wrapper = get_sdk_wrapper()
            if not self._sdk_wrapper.is_initialized:
                await self._sdk_wrapper.initialize()
        return self._sdk_wrapper

    async def generate_components(
        self,
        skill: A2UISkillMeta,
        question: str,
        context: Dict[str, Any],
    ) -> List[WidgetSelection]:
        """
        Generate dashboard components using LLM tool call.

        Method: generate_components - LLM-powered widget generation.
        Called from: A2UIRuntime._stream_component_selection
        Invokes: build_llm_component_tool, A2UISDKWrapper.query
        Why: Generates contextual component IDs and bindings based on user query.

        Args:
            skill: The selected A2UI skill
            question: User's original question
            context: Render context with tickers, metrics, etc.

        Returns:
            List of validated WidgetSelection objects
        """
        # Check for backward compatibility - if skill has component_tree, use it
        component_tree = skill.layout_config.get("component_tree") if skill.layout_config else None
        if component_tree:
            logger.info(
                "[LLM_GENERATOR] Skill %s has component_tree, using static layout",
                skill.skill_id
            )
            return get_components_from_tree(skill, component_tree)

        # Generate components via LLM
        try:
            wrapper = await self._get_sdk_wrapper()

            tickers = context.get("tickers", [])
            primary_ticker = context.get("primary_ticker", tickers[0] if tickers else "")
            metric = context.get("metric", "")
            time_range = context.get("time_range", "1Y")

            prompt = f"""Generate dashboard components for this question:

Question: {question}
Primary Ticker: {primary_ticker}
All Tickers: {', '.join(tickers)}
Metric Focus: {metric}
Time Range: {time_range}
Skill: {skill.name}

Available Widgets: {', '.join(set(skill.widgets))}

Valid Data Paths:
{json.dumps(skill.all_data_paths, indent=2)}

Widget Binding Rules:
{json.dumps(skill.widget_bindings, indent=2)}

Create 3-6 components with:
1. Meaningful IDs (e.g., 'kpi_amd_revenue', 'chart_peer_comparison')
2. Correct data bindings from the paths above
3. Appropriate priorities (0=top, 100=bottom)

Also suggest 1-2 follow_up_actions for continuous analysis.

Call the generate_dashboard_components tool with your selection."""

            response = await wrapper.query(
                prompt=prompt,
                tools=[build_llm_component_tool(skill)],
                max_tokens=1500,
                temperature=0.3,
                tool_choice={"type": "any"},  # Force tool use
            )

            return self._parse_and_validate(response, skill)

        except Exception as e:
            logger.warning("[LLM_GENERATOR] LLM generation failed: %s, falling back", e)
            return self._generate_fallback(skill, context)

    def _parse_and_validate(
        self,
        response: Any,
        skill: A2UISkillMeta,
    ) -> List[WidgetSelection]:
        """
        Parse LLM tool response and validate components.

        Method: _parse_and_validate - extracts and validates LLM output.
        Called from: generate_components
        Invokes: validate_llm_components
        Why: Ensures LLM output conforms to skill schema.
        """
        try:
            # Handle response based on type
            if hasattr(response, 'tool_calls') and response.tool_calls:
                # Extract tool call result
                tool_result = response.tool_calls[0]
                if hasattr(tool_result, 'input'):
                    data = tool_result.input
                elif isinstance(tool_result, dict):
                    data = tool_result.get("input", tool_result)
                else:
                    data = {}
            elif hasattr(response, 'content') and response.content:
                # Try to parse JSON from content
                content = response.content
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    data = json.loads(content[start_idx:end_idx])
                else:
                    data = {}
            else:
                data = {}

            components = data.get("components", [])
            if not components:
                logger.warning("[LLM_GENERATOR] No components in LLM response")
                return []

            # Validate components
            valid_widgets, errors = validate_llm_components(components, skill)

            if errors:
                logger.warning(
                    "[LLM_GENERATOR] Validation errors: %s",
                    errors[:5]
                )

            if valid_widgets:
                logger.info(
                    "[LLM_GENERATOR] Generated %d valid components: %s",
                    len(valid_widgets),
                    [w.widget_id for w in valid_widgets]
                )

                # Store follow-up actions if present
                follow_ups = data.get("follow_up_actions", [])
                if follow_ups:
                    logger.info(
                        "[LLM_GENERATOR] Follow-up actions: %s",
                        [f.get("label") for f in follow_ups]
                    )

            return valid_widgets

        except Exception as e:
            logger.warning("[LLM_GENERATOR] Parse error: %s", e)
            return []

    def _generate_fallback(
        self,
        skill: A2UISkillMeta,
        context: Dict[str, Any],
    ) -> List[WidgetSelection]:
        """
        Generate fallback components when LLM fails.

        Method: _generate_fallback - creates default layout from widget_bindings.
        Called from: generate_components (on LLM failure)
        Invokes: skill.widget_bindings
        Why: Ensures dashboard renders even when LLM unavailable.
        """
        widgets: List[WidgetSelection] = []
        seen_types: set = set()
        priority = 0

        # Get unique widget types from skill
        unique_types = list(dict.fromkeys(skill.widgets))  # Preserve order, remove dupes

        for widget_type in unique_types:
            if widget_type in seen_types:
                continue
            seen_types.add(widget_type)

            # Build default bindings from widget_bindings schema
            bindings = self._build_default_bindings(widget_type, skill)

            widget_id = f"{widget_type.lower()}_{len(widgets)}"

            widgets.append(WidgetSelection(
                widget_type=widget_type,
                widget_id=widget_id,
                data_bindings=bindings,
                priority=priority,
            ))
            priority += 10

        logger.info(
            "[LLM_GENERATOR] Fallback generated %d widgets: %s",
            len(widgets),
            [w.widget_id for w in widgets]
        )

        return widgets

    def _build_default_bindings(
        self,
        widget_type: str,
        skill: A2UISkillMeta,
    ) -> Dict[str, Any]:
        """
        Build default data bindings from widget_bindings schema.

        Method: _build_default_bindings - extracts paths from skill config.
        Called from: _generate_fallback
        Invokes: skill.widget_bindings
        Why: Creates sensible defaults when LLM doesn't specify bindings.
        """
        bindings: Dict[str, Any] = {}
        rules = skill.widget_bindings.get(widget_type, {})

        # Map common binding keys to property names
        key_to_prop = {
            "valid_value_paths": "value",
            "valid_delta_paths": "delta",
            "valid_label_paths": "label",
            "valid_series_path": "series",
            "valid_annotations_path": "annotations",
            "valid_title_path": "title",
            "valid_columns_path": "columns",
            "valid_data_path": "data",
            "valid_events_path": "items",
            "valid_ticker_path": "ticker",
            "valid_tickers_path": "tickers",
            "valid_explanation_path": "explanation",
            "valid_factors_path": "factors",
            "valid_citations_path": "citations",
            "valid_matrix_path": "matrix",
            "valid_chart_path": "chart",
            "valid_table_path": "table",
        }

        for key, prop_name in key_to_prop.items():
            if key in rules:
                value = rules[key]
                if isinstance(value, list) and value:
                    # Use first valid path
                    bindings[prop_name] = {"path": value[0]}
                elif isinstance(value, str) and value.startswith("/"):
                    bindings[prop_name] = {"path": value}

        return bindings


def get_components_from_tree(
    skill: A2UISkillMeta,
    component_tree: Dict[str, Any],
) -> List[WidgetSelection]:
    """
    Extract widget selections from a static component_tree.

    Function: get_components_from_tree - backward compat for component_tree skills.
    Called from: LLMComponentGenerator.generate_components
    Invokes: n/a
    Why: Supports existing skills with component_tree (e.g., explain_move).
    """
    widgets: List[WidgetSelection] = []

    for comp_id, comp_def in component_tree.items():
        comp_type = comp_def.get("type")

        # Skip layout components (Row, Column, Card)
        if comp_type in ("Row", "Column", "Card", "Text"):
            continue

        # Skip if not in skill's widget list
        if comp_type not in skill.widgets:
            continue

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
            priority=len(widgets) * 10,
        ))

    logger.info(
        "[TREE_EXTRACT] Extracted %d widgets from component_tree: %s",
        len(widgets),
        [w.widget_id for w in widgets]
    )

    return widgets


# Singleton for LLM generator
_llm_generator: Optional[LLMComponentGenerator] = None


def get_llm_component_generator() -> LLMComponentGenerator:
    """Get the LLM component generator singleton."""
    global _llm_generator
    if _llm_generator is None:
        _llm_generator = LLMComponentGenerator()
    return _llm_generator


__all__ = [
    "WidgetSelection",
    "WidgetTypeSelection",
    "DashboardLayout",
    "ComponentSelector",
    "get_component_selector",
    "get_components_by_types",
    "build_component_selection_tool",
    "LLMComponentGenerator",
    "get_llm_component_generator",
    "build_llm_component_tool",
    "validate_llm_components",
    "get_components_from_tree",
]
