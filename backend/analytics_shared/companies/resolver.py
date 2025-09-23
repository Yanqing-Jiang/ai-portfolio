"""
Company Resolution Shared Functions

Contains shared company alias resolution and ticker validation functions used by both
analytics_memory and analytics_supervisor systems.
"""

from typing import Dict, Any, List, Optional


def resolve_alias_to_ticker(company_input: str, configs: Dict[str, Any]) -> Optional[str]:
    """
    Resolve a company alias (name, short name, or alias) to its official ticker.

    Args:
        company_input: User input like "Micron", "nvidia", "Advanced Micro Devices"
        configs: Configuration dictionary containing companies data

    Returns:
        Official ticker symbol if found, None if not found
    """
    if not company_input or not isinstance(company_input, str):
        return None

    # Clean input - strip whitespace and normalize case
    clean_input = company_input.strip().lower()

    # Get companies data from config
    companies_data = configs.get('companies', {}).get('companies', {})

    # Search through all sectors
    for sector_name, companies_list in companies_data.items():
        if not isinstance(companies_list, list):
            continue

        for company in companies_list:
            if not isinstance(company, dict):
                continue

            ticker = company.get('ticker', '')

            # Check exact ticker match (case insensitive)
            if ticker.lower() == clean_input:
                return ticker

            # Check company name match (case insensitive)
            company_name = company.get('name', '').lower()
            if company_name == clean_input:
                return ticker

            # Check short name match (case insensitive)
            short_name = company.get('short_name', '').lower()
            if short_name == clean_input:
                return ticker

            # Check aliases match (case insensitive)
            aliases = company.get('aliases', [])
            if isinstance(aliases, list):
                for alias in aliases:
                    if isinstance(alias, str) and alias.lower() == clean_input:
                        return ticker

    return None