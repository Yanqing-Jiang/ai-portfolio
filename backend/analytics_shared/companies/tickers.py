"""
Ticker Utilities Shared Functions

Contains shared ticker sanitization and validation functions used by both
analytics_memory and analytics_supervisor systems.
"""

from typing import Dict, Any, List, Optional


def get_ticker_list(configs: Dict[str, Any]) -> List[str]:
    """
    Get list of allowed ticker symbols from configuration.

    Args:
        configs: Configuration dictionary

    Returns:
        List of ticker symbols
    """
    tickers = (
        configs.get('companies', {})
        .get('selection_rules', {})
        .get('default_companies', {})
        .get('tickers', ["NVDA", "AMD", "INTC", "MU", "QCOM", "AVGO", "TXN"])
    )
    return tickers


def sanitize_ticker(raw_ticker: str, allowed_tickers: List[str]) -> Optional[str]:
    """
    Sanitize ticker symbol to prevent SQL injection.

    Args:
        raw_ticker: The raw ticker input from user
        allowed_tickers: List of allowed ticker symbols

    Returns:
        Sanitized ticker symbol if valid, None if invalid
    """
    if not raw_ticker or not isinstance(raw_ticker, str):
        return None

    # Convert to uppercase and strip whitespace
    clean_ticker = raw_ticker.strip().upper()

    # Only allow alphanumeric characters (typical ticker format)
    if not clean_ticker.isalnum():
        return None

    # Check if ticker is in allowed list
    if clean_ticker in allowed_tickers:
        return clean_ticker

    # Return None if not found in allowed list
    return None


def validate_and_resolve_company(raw_company: str, configs: Dict[str, Any]) -> Optional[str]:
    """
    Validate and resolve company input to a ticker symbol.

    Args:
        raw_company: Raw company input from user
        configs: Configuration dictionary

    Returns:
        Validated ticker symbol or None if invalid
    """
    if not raw_company:
        return None

    # Import here to avoid circular imports
    from .resolver import resolve_alias_to_ticker

    # First try alias resolution (handles names like "Micron", "nvidia")
    target_ticker = resolve_alias_to_ticker(raw_company, configs)

    # If alias resolution didn't work, try direct ticker validation
    if not target_ticker:
        allowed_tickers = get_ticker_list(configs)
        target_ticker = sanitize_ticker(raw_company, allowed_tickers)

    return target_ticker


def format_company_error(raw_company: str, configs: Dict[str, Any]) -> str:
    """
    Format a helpful error message for unrecognized companies.

    Args:
        raw_company: The invalid company input
        configs: Configuration dictionary

    Returns:
        Formatted error message
    """
    tickers = get_ticker_list(configs)

    if not raw_company:
        return "This query requires specifying a company. Please mention a company ticker (e.g., 'NVDA', 'AMD') or company name (e.g., 'Nvidia', 'Micron') in your query."

    # Try to get company names for display
    try:
        companies_data = configs.get('companies', {}).get('companies', {}).get('semiconductor', [])
        available_companies = []
        for i, ticker in enumerate(tickers[:5]):  # Show first 5
            if i < len(companies_data):
                short_name = companies_data[i].get('short_name', ticker)
                available_companies.append(f"{ticker} ({short_name})")
            else:
                available_companies.append(ticker)

        return f"Company '{raw_company}' not recognized. Available companies: {', '.join(available_companies)}..."
    except Exception:
        # Fallback to just ticker list
        return f"Company '{raw_company}' not recognized. Available tickers: {', '.join(tickers[:5])}..."