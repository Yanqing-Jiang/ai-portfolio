"""
A2UI Component Catalog

Defines the custom financial components that extend the standard A2UI catalog.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel


class ComponentProperty(BaseModel):
    """Property definition for a catalog component."""
    type: str  # BoundString, BoundNumber, BoundBoolean, BoundArray
    required: bool = False
    default: Optional[str] = None
    enum: Optional[List[str]] = None
    description: Optional[str] = None


class ComponentDefinition(BaseModel):
    """Definition of a catalog component."""
    description: str
    properties: Dict[str, ComponentProperty]


class CatalogDefinition(BaseModel):
    """Full catalog definition document."""
    catalogId: str
    extends: Optional[str] = None
    components: Dict[str, ComponentDefinition]


# ============================================================================
# Financial Catalog Definition
# ============================================================================

FINANCIAL_CATALOG = CatalogDefinition(
    catalogId="https://yoursite.com/a2ui/financial-catalog/v1.0",
    extends="https://github.com/google/A2UI/blob/main/specification/0.8/json/standard_catalog_definition.json",
    components={
        "PriceChart": ComponentDefinition(
            description="TradingView-powered candlestick chart for stock price visualization",
            properties={
                "ticker": ComponentProperty(
                    type="BoundString",
                    required=True,
                    description="Stock ticker symbol (e.g., NVDA, AAPL)"
                ),
                "interval": ComponentProperty(
                    type="BoundString",
                    required=False,
                    default="1D",
                    enum=["1D", "1W", "1M", "3M", "6M", "1Y", "5Y"],
                    description="Time interval for the chart"
                ),
                "showVolume": ComponentProperty(
                    type="BoundBoolean",
                    required=False,
                    default="true",
                    description="Whether to show volume bars"
                ),
            }
        ),
        "KpiCard": ComponentDefinition(
            description="Single metric KPI display with optional delta indicator",
            properties={
                "label": ComponentProperty(
                    type="BoundString",
                    required=True,
                    description="Label for the KPI"
                ),
                "value": ComponentProperty(
                    type="BoundNumber",
                    required=True,
                    description="The numeric value to display"
                ),
                "unit": ComponentProperty(
                    type="BoundString",
                    required=False,
                    description="Unit suffix (e.g., $, %, M)"
                ),
                "delta": ComponentProperty(
                    type="BoundNumber",
                    required=False,
                    description="Change value for trend indicator"
                ),
                "deltaType": ComponentProperty(
                    type="BoundString",
                    required=False,
                    enum=["percentage", "absolute"],
                    description="How to format the delta"
                ),
            }
        ),
        "DataTable": ComponentDefinition(
            description="Sortable financial data table with column definitions",
            properties={
                "columns": ComponentProperty(
                    type="BoundArray",
                    required=True,
                    description="Array of column definitions [{key, label, type}]"
                ),
                "data": ComponentProperty(
                    type="BoundArray",
                    required=True,
                    description="Array of row objects"
                ),
                "sortable": ComponentProperty(
                    type="BoundBoolean",
                    required=False,
                    default="true",
                    description="Whether columns are sortable"
                ),
            }
        ),
        "NewsTimeline": ComponentDefinition(
            description="Vertical timeline of news events with sentiment indicators",
            properties={
                "events": ComponentProperty(
                    type="BoundArray",
                    required=True,
                    description="Array of event objects [{date, title, summary, sentiment, source}]"
                ),
            }
        ),
        "CorrelationMatrix": ComponentDefinition(
            description="ECharts heatmap visualization for asset correlations",
            properties={
                "tickers": ComponentProperty(
                    type="BoundArray",
                    required=True,
                    description="Array of ticker symbols for axes"
                ),
                "matrix": ComponentProperty(
                    type="BoundArray",
                    required=True,
                    description="2D array of correlation values (-1 to 1)"
                ),
            }
        ),
        "ExplainMovePanel": ComponentDefinition(
            description="AI explanation panel for price movements with citations",
            properties={
                "title": ComponentProperty(
                    type="BoundString",
                    required=True,
                    description="Panel title"
                ),
                "explanation": ComponentProperty(
                    type="BoundString",
                    required=True,
                    description="AI-generated explanation text"
                ),
                "factors": ComponentProperty(
                    type="BoundArray",
                    required=False,
                    description="Array of contributing factors [{factor, impact, source}]"
                ),
                "citations": ComponentProperty(
                    type="BoundArray",
                    required=False,
                    description="Array of source citations [{title, url, date}]"
                ),
            }
        ),
        "ErrorPanel": ComponentDefinition(
            description="Displays structured error codes/messages from backend validation",
            properties={
                "code": ComponentProperty(
                    type="BoundString",
                    required=True,
                    description="Machine-readable error code"
                ),
                "message": ComponentProperty(
                    type="BoundString",
                    required=True,
                    description="Human-readable error message"
                ),
                "details": ComponentProperty(
                    type="BoundString",
                    required=False,
                    description="Optional additional details"
                ),
            }
        ),
        "MetricChart": ComponentDefinition(
            description="ECharts-based time-series chart for financial metrics (revenue, margins, etc.)",
            properties={
                "title": ComponentProperty(
                    type="BoundString",
                    required=False,
                    description="Chart title"
                ),
                "series": ComponentProperty(
                    type="BoundArray",
                    required=True,
                    description="Array of series [{ticker, data: [{period, value}]}]"
                ),
                "metric": ComponentProperty(
                    type="BoundString",
                    required=False,
                    default="Value",
                    description="Y-axis label (e.g., Revenue, Margin %)"
                ),
                "chartType": ComponentProperty(
                    type="BoundString",
                    required=False,
                    default="line",
                    enum=["line", "bar", "area"],
                    description="Chart visualization type"
                ),
                "annotations": ComponentProperty(
                    type="BoundArray",
                    required=False,
                    description="Array of annotations [{period, ticker, label, details}]"
                ),
            }
        ),
    }
)


class FinancialCatalog:
    """
    Financial component catalog for A2UI.
    
    Provides validation and introspection of available components.
    """
    
    def __init__(self):
        self.definition = FINANCIAL_CATALOG
    
    @property
    def catalog_id(self) -> str:
        return self.definition.catalogId
    
    @property
    def component_names(self) -> List[str]:
        return list(self.definition.components.keys())
    
    def get_component(self, name: str) -> Optional[ComponentDefinition]:
        return self.definition.components.get(name)
    
    def validate_component(self, name: str, props: Dict) -> List[str]:
        """
        Validate component properties against the catalog.
        
        Returns list of validation errors (empty if valid).
        """
        errors = []
        component = self.get_component(name)
        
        if not component:
            errors.append(f"Unknown component type: {name}")
            return errors
        
        # Check required properties
        for prop_name, prop_def in component.properties.items():
            if prop_def.required and prop_name not in props:
                errors.append(f"Missing required property: {prop_name}")
        
        # Check unknown properties
        known_props = set(component.properties.keys())
        for prop_name in props:
            if prop_name not in known_props:
                errors.append(f"Unknown property: {prop_name}")
        
        # Check enum values
        for prop_name, prop_value in props.items():
            prop_def = component.properties.get(prop_name)
            if prop_def and prop_def.enum:
                # Extract literal value if bound
                if isinstance(prop_value, dict):
                    literal = prop_value.get("literalString")
                    if literal and literal not in prop_def.enum:
                        errors.append(f"Invalid value for {prop_name}: {literal}. Must be one of {prop_def.enum}")
        
        return errors
    
    def to_prompt_context(self) -> str:
        """
        Generate a description of available components for LLM prompts.
        """
        lines = ["Available dashboard components:"]
        
        for name, comp in self.definition.components.items():
            lines.append(f"\n## {name}")
            lines.append(comp.description)
            lines.append("Properties:")
            for prop_name, prop_def in comp.properties.items():
                required = " (required)" if prop_def.required else ""
                default = f" [default: {prop_def.default}]" if prop_def.default else ""
                enum = f" - one of: {prop_def.enum}" if prop_def.enum else ""
                lines.append(f"  - {prop_name}: {prop_def.type}{required}{default}{enum}")
                if prop_def.description:
                    lines.append(f"    {prop_def.description}")
        
        return "\n".join(lines)


# Singleton instance
_catalog: Optional[FinancialCatalog] = None


def get_catalog() -> FinancialCatalog:
    """Get the financial catalog singleton."""
    global _catalog
    if _catalog is None:
        _catalog = FinancialCatalog()
    return _catalog
