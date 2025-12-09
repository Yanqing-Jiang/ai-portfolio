"""TradingView Configuration Tool for Conversational Analytics."""
from __future__ import annotations

from typing import Any, Dict, Optional

# Tool definition for Claude
TRADINGVIEW_TOOL_DEFINITION = {
    "name": "create_tradingview_chart",
    "description": """Generate a TradingView widget configuration for displaying stock charts.

Use this tool when the user wants to see a stock chart, price history, or technical analysis visualization.
The generated configuration will be rendered as an interactive TradingView widget in the frontend.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Stock ticker symbol (e.g., 'NVDA', 'AMD', 'AAPL')"
            },
            "interval": {
                "type": "string",
                "enum": ["1", "5", "15", "30", "60", "D", "W", "M"],
                "description": "Chart interval: 1/5/15/30/60 minutes, D=daily, W=weekly, M=monthly"
            },
            "chart_type": {
                "type": "string",
                "enum": ["candlestick", "line", "area", "bars"],
                "description": "Type of chart to display"
            },
            "show_volume": {
                "type": "boolean",
                "description": "Whether to show volume bars"
            }
        },
        "required": ["symbol"]
    }
}

# Chart type mapping
CHART_STYLES = {
    "candlestick": "1",
    "line": "2",
    "area": "3",
    "bars": "0"
}


def generate_tradingview_config(
    symbol: str,
    interval: str = "D",
    chart_type: str = "candlestick",
    show_volume: bool = True,
    container_id: Optional[str] = None
) -> Dict[str, Any]:
    """Generate TradingView widget configuration.
    
    Args:
        symbol: Stock ticker symbol
        interval: Chart interval
        chart_type: Type of chart (candlestick, line, area, bars)
        show_volume: Whether to show volume
        container_id: Optional container element ID
        
    Returns:
        TradingView widget configuration dictionary
    """
    # Normalize symbol for TradingView
    symbol_clean = symbol.upper().strip()
    
    # Add exchange prefix if not present
    if ":" not in symbol_clean:
        # Default to NASDAQ for common tech stocks
        nasdaq_stocks = ["NVDA", "AMD", "INTC", "AVGO", "QCOM", "MU", "TXN", "AAPL", "MSFT", "GOOGL", "AMZN", "META"]
        if symbol_clean in nasdaq_stocks:
            symbol_full = f"NASDAQ:{symbol_clean}"
        else:
            symbol_full = f"NYSE:{symbol_clean}"
    else:
        symbol_full = symbol_clean
    
    style = CHART_STYLES.get(chart_type, "1")
    
    config = {
        "widget_type": "tradingview",  # Identifies this as a TradingView widget for frontend
        "symbol": symbol_full,
        "interval": interval,
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": style,
        "locale": "en",
        "toolbar_bg": "#1e1e1e",
        "enable_publishing": False,
        "hide_side_toolbar": False,
        "hide_top_toolbar": False,
        "allow_symbol_change": True,
        "save_image": False,
        "withdateranges": True,
        "support_host": "https://www.tradingview.com",
        "container_id": container_id or f"tradingview_{symbol_clean}",
        "width": "100%",
        "height": 400,
        "hide_volume": not show_volume,
        # Additional studies/indicators can be added
        "studies": [],
        # Widget script URL for embedding
        "widget_url": "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js",
    }
    
    return config


async def execute_tradingview_tool(
    symbol: str,
    interval: str = "D",
    chart_type: str = "candlestick",
    show_volume: bool = True
) -> Dict[str, Any]:
    """Execute the TradingView tool and return configuration.
    
    Args:
        symbol: Stock ticker symbol
        interval: Chart interval
        chart_type: Type of chart
        show_volume: Whether to show volume
        
    Returns:
        Dictionary with success status and chart configuration
    """
    try:
        config = generate_tradingview_config(
            symbol=symbol,
            interval=interval,
            chart_type=chart_type,
            show_volume=show_volume
        )
        
        return {
            "success": True,
            "config": config,
            "symbol": symbol,
            "chart_type": chart_type
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol
        }
