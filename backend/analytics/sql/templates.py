# --- Analytics Function/Class Map ---
# Function: fetch_templates_for_intent
#   Role: Return YAML-backed template suggestions for the supplied intent.
#   Called from: analytics.flows.planner_executor, analytics.sql.prompt_builder
#   Invokes: analytics.core.config_store.get_config_store
#   Why: Supports downstream analytics workflows that rely on fetch_templates_for_intent.
# Function: summarize_template
#   Role: Handles summarize template logic for analytics.sql.templates.
#   Called from: analytics.sql.prompt_builder
#   Invokes: Internal helpers only
#   Why: Keeps analytics.sql.templates from duplicating summarize template behavior across flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.config_store import ConfigStore, get_config_store
from ..core.state import IntentModel


async def fetch_templates_for_intent(
    intent: IntentModel,
    *,
    query: Optional[str] = None,
    top_k: int = 3,
    store: Optional[ConfigStore] = None,
) -> List[Dict[str, Any]]:
    """Return YAML-backed template suggestions for the supplied intent."""
    store = store or get_config_store()
    search_query = query or intent.intent_key or intent.slots_detected.get("original_query", "")
    result = await store.get_templates(
        query=search_query or "financial analytics",
        intent_key=intent.intent_key,
        top_k=top_k,
    )
    return result.data


def summarize_template(template: Dict[str, Any]) -> str:
    name = template.get("name") or template.get("id") or "unknown"
    description = template.get("description", "")
    highlights = template.get("highlights") or template.get("keywords") or []
    highlights_text = ", ".join(highlights) if highlights else ""
    lines = [f"Template: {name}"]
    if description:
        lines.append(f"Description: {description}")
    if highlights_text:
        lines.append(f"Highlights: {highlights_text}")
    if template.get("sql_template"):
        sample = template["sql_template"].strip()
        if len(sample) > 280:
            sample = sample[:280] + "..."
        lines.append(f"SQL Pattern:\n{sample}")
    return "\n".join(lines)
