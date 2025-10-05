import re

from analytics.core.config import CONFIGS

PLACEHOLDER_SLOT_MAP = {
    "target_ticker": "company",
    "start_year": "timeframe.start_year",
}


def _placeholders_from_template(template: str) -> set[str]:
    pattern = re.compile(r"\{([a-zA-Z0-9_\.]+)\}")
    return {match.group(1) for match in pattern.finditer(template or "")}


def test_query_templates_cover_required_placeholders():
    query_patterns = CONFIGS.queries.get("query_patterns", {})
    requirements = CONFIGS.query_requirements.get("required_slots", {})

    for intent_key, template_entry in query_patterns.items():
        required = set(requirements.get(intent_key, []) or [])
        sql_templates = [template_entry.get("sql_template", "")]
        if template_entry.get("single_year_template"):
            sql_templates.append(template_entry["single_year_template"])
        placeholders = set()
        for sql in sql_templates:
            placeholders |= _placeholders_from_template(sql)

        for placeholder, required_slot in PLACEHOLDER_SLOT_MAP.items():
            if placeholder in placeholders:
                assert required_slot in required, (
                    f"Intent '{intent_key}' references placeholder '{placeholder}' but missing required slot '{required_slot}'"
                )
