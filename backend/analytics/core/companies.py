from __future__ import annotations

from typing import Any, Dict, List, Optional


def get_ticker_list(configs: Dict[str, Any]) -> List[str]:
    return (
        configs.get('companies', {})
        .get('selection_rules', {})
        .get('default_companies', {})
        .get('tickers', ["NVDA", "AMD", "INTC", "MU", "QCOM", "AVGO", "TXN"])
    )


def resolve_alias_to_ticker(company_input: str, configs: Dict[str, Any]) -> Optional[str]:
    if not company_input or not isinstance(company_input, str):
        return None
    clean_input = company_input.strip().lower()
    companies_data = configs.get('companies', {}).get('companies', {})
    for companies_list in companies_data.values():
        if not isinstance(companies_list, list):
            continue
        for company in companies_list:
            if not isinstance(company, dict):
                continue
            ticker = company.get('ticker', '')
            if ticker.lower() == clean_input:
                return ticker
            if company.get('name', '').lower() == clean_input:
                return ticker
            if company.get('short_name', '').lower() == clean_input:
                return ticker
            aliases = company.get('aliases', [])
            if isinstance(aliases, list) and any(isinstance(alias, str) and alias.lower() == clean_input for alias in aliases):
                return ticker
    return None


def sanitize_ticker(raw_ticker: str, allowed_tickers: List[str]) -> Optional[str]:
    if not raw_ticker or not isinstance(raw_ticker, str):
        return None
    clean_ticker = raw_ticker.strip().upper()
    if not clean_ticker.isalnum():
        return None
    return clean_ticker if clean_ticker in allowed_tickers else None


def validate_and_resolve_company(raw_company: str, configs: Dict[str, Any]) -> Optional[str]:
    if not raw_company:
        return None
    ticker = resolve_alias_to_ticker(raw_company, configs)
    if ticker:
        return ticker
    allowed = get_ticker_list(configs)
    return sanitize_ticker(raw_company, allowed)


def format_company_error(raw_company: str, configs: Dict[str, Any]) -> str:
    tickers = get_ticker_list(configs)
    if not raw_company:
        return "This query requires specifying a company (e.g., 'NVDA', 'AMD')."
    companies_data = configs.get('companies', {}).get('companies', {}).get('semiconductor', [])
    samples: List[str] = []
    for i, ticker in enumerate(tickers[:5]):
        if i < len(companies_data):
            short_name = companies_data[i].get('short_name') or ticker
            samples.append(f"{ticker} ({short_name})")
        else:
            samples.append(ticker)
    sample_text = ', '.join(samples) or ', '.join(tickers[:5])
    return f"Company '{raw_company}' not recognized. Available examples: {sample_text}"
