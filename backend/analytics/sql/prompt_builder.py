from __future__ import annotations

from textwrap import dedent
from typing import Any, Dict, List, Optional

from ..core.config_store import ConfigStore, get_config_store
from ..core.context import get_configs
from ..core.state import IntentModel, QueryPlanModel
from .templates import fetch_templates_for_intent, summarize_template

CONFIGS = get_configs()


def _render_metrics_summary(plan: QueryPlanModel) -> str:
    metrics_catalog = CONFIGS.metrics.get("metrics", {}) or {}
    summaries: List[str] = []
    for metric_name in plan.metrics or []:
        metric = None
        for key, value in metrics_catalog.items():
            if key.lower() == metric_name.lower() or value.get("name", "").lower() == metric_name.lower():
                metric = {"id": key, **value}
                break
        if not metric:
            summaries.append(f"- {metric_name}")
            continue
        alias_text = ", ".join(metric.get("aliases", [])) if metric.get("aliases") else ""
        detail = f"- {metric.get('name', metric_name)} (db: {metric.get('database_name', metric_name)})"
        if alias_text:
            detail += f" | aliases: {alias_text}"
        if metric.get("description"):
            detail += f" | desc: {metric['description']}"
        summaries.append(detail)
    return "\n".join(summaries)


def _render_constraints(plan: QueryPlanModel) -> str:
    database_cfg = CONFIGS.database or {}
    defaults = database_cfg.get("query_defaults", {})
    allowed_tables = list((database_cfg.get("tables") or {}).keys()) or ["comp_financials"]
    default_limit = defaults.get("default_limit", 500)
    limit_guard = default_limit
    plan_limit = getattr(plan, "limit", None) if plan else None
    if isinstance(plan_limit, int) and plan_limit > 0:
        limit_guard = min(limit_guard, plan_limit)
    default_years_back = defaults.get("default_years_back", plan.timeframe.years_back if plan.timeframe else 5)
    return dedent(
        f"""
        Allowed tables: {', '.join(allowed_tables)}
        Required filters:
          - Must restrict calendar_year using >= CURRENT_YEAR - {default_years_back}
          - Must include calendar_year in SELECT list
          - If granularity is quarterly, include calendar_quarter_num and calendar_quarter in SELECT and GROUP BY
        Limits:
          - Always include LIMIT <= {limit_guard}
          - Planner default LIMIT guardrail: {default_limit}
        Safety:
          - No DDL/DML statements
          - No CROSS JOIN unless justified by templates
          - Use parameterized literals, avoid string concatenation
        """
    ).strip()


async def build_sql_messages(
    *,
    original_query: str,
    intent: IntentModel,
    plan: QueryPlanModel,
    config_store: Optional[ConfigStore] = None,
    templates: Optional[List[Dict[str, Any]]] = None,
    top_k_templates: int = 2,
) -> List[Dict[str, str]]:
    """Construct system/user messages guiding an LLM to draft SQL."""
    store = config_store or get_config_store()
    candidate_templates = templates
    if candidate_templates is None:
        candidate_templates = await fetch_templates_for_intent(
            intent,
            query=original_query,
            top_k=top_k_templates,
            store=store,
        )
    template_blocks = [summarize_template(template) for template in candidate_templates]
    template_text = "\n\n".join(template_blocks) if template_blocks else "(No template match; use best judgment)"

    metrics_summary = _render_metrics_summary(plan)
    constraints_text = _render_constraints(plan)

    slot_lines = []
    for key, value in (intent.slots_detected or {}).items():
        if key == "original_query":
            continue
        slot_lines.append(f"- {key}: {value}")
    slots_section = "\n".join(slot_lines) if slot_lines else "- none captured"

    system_prompt = dedent(
        """
        You are an expert financial data engineer. Generate safe SQL for PostgreSQL using only the allowed tables.
        Obey all instructions, especially filters and limits. Respond with SQL only, wrapped in triple backticks, with no commentary.

        PostgreSQL-specific rules:
        - For rounding decimals, use ROUND(CAST(value AS numeric), precision) not ROUND(value, precision)
        - Division of integers produces integer results; cast to numeric for decimal results
        - Use EXTRACT(YEAR FROM CURRENT_DATE) for current year
        """
    ).strip()

    user_prompt = dedent(
        f"""
        USER QUESTION:
        {original_query}

        DETECTED INTENT: {intent.intent_key} (confidence {intent.confidence:.2f})
        SLOTS:
        {slots_section}

        QUERY PLAN:
        - Metrics: {', '.join(plan.metrics or [])}
        - Derived Metrics: {', '.join(plan.derived_metrics or []) or 'none'}
        - Granularity: {plan.granularity}
        - Comparison: {plan.comparison or 'n/a'}
        - Years Back: {plan.timeframe.years_back if plan.timeframe else 'default'}
        - Group By: {', '.join(plan.group_by or [])}

        METRIC DETAILS:
        {metrics_summary or '- unavailable'}

        TEMPLATE SUGGESTIONS:
        {template_text}

        RULES:
        {constraints_text}

        OUTPUT FORMAT:
        ```sql
        SELECT ...
        ```
        """
    ).strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


async def build_sql_retry_messages(
    *,
    original_query: str,
    intent: IntentModel,
    plan: QueryPlanModel,
    error_code: str,
    error_detail: str,
    previous_sql: Optional[str],
    attempts: List[Dict[str, Any]],
    config_store: Optional[ConfigStore] = None,
    templates: Optional[List[Dict[str, Any]]] = None,
    top_k_templates: int = 2,
) -> List[Dict[str, str]]:
    """Construct retry-oriented messages for the SQL query agent."""
    store = config_store or get_config_store()
    candidate_templates = templates
    if candidate_templates is None:
        candidate_templates = await fetch_templates_for_intent(
            intent,
            query=original_query,
            top_k=top_k_templates,
            store=store,
        )
    template_blocks = [summarize_template(template) for template in candidate_templates]
    template_text = "\n\n".join(template_blocks) if template_blocks else "(No template match; rely on reasoning)"

    metrics_summary = _render_metrics_summary(plan)
    constraints_text = _render_constraints(plan)

    history_lines: List[str] = []
    for attempt in attempts or []:
        idx = attempt.get("attempt")
        source = attempt.get("source", "unknown")
        status = attempt.get("status", "unknown")
        code = attempt.get("error_code")
        detail = attempt.get("error_detail")
        preview = attempt.get("sql_preview")
        line = f"Attempt {idx} [{source}] -> {status}"
        if code:
            line += f" ({code})"
        if detail:
            line += f" | {detail}"
        if preview:
            line += f" | SQL: {preview}"
        history_lines.append(line)
    history_text = "\n".join(history_lines) if history_lines else "No previous attempts recorded."

    truncated_sql = (previous_sql[:500] + "...") if previous_sql and len(previous_sql) > 500 else (previous_sql or "n/a")

    system_prompt = dedent(
        """
        You are a senior analytics query agent tasked with fixing SQL that previously failed.
        Produce safe, efficient PostgreSQL.
        Return SQL only, wrapped in triple backticks. No commentary.
        """
    ).strip()

    user_prompt = dedent(
        f"""
        USER QUESTION:
        {original_query}

        DETECTED INTENT: {intent.intent_key} (confidence {intent.confidence:.2f})
        PLAN GRANULARITY: {plan.granularity}
        PLAN COMPARISON: {plan.comparison or 'n/a'}
        METRICS: {', '.join(plan.metrics or []) or 'n/a'}
        GROUP BY: {', '.join(plan.group_by or []) or 'n/a'}

        LAST ERROR CODE: {error_code or 'unknown'}
        LAST ERROR DETAIL: {error_detail or 'n/a'}
        PRIOR SQL (truncated):
        {truncated_sql}

        PREVIOUS ATTEMPTS:
        {history_text}

        TEMPLATE SUGGESTIONS:
        {template_text}

        RULES:
        {constraints_text}

        OUTPUT:
        ```sql
        SELECT ...
        ```
        """
    ).strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def extract_sql_from_response(content: str) -> str:
    """Extract SQL from an LLM response that may include formatting."""
    content = content.strip()
    if not content:
        return content

    if "```" in content:
        segments = content.split("```")
        for idx in range(1, len(segments), 2):
            block = segments[idx]
            block_stripped = block.lstrip()
            if block_stripped.lower().startswith("sql"):
                block_stripped = block_stripped[3:]
            block_stripped = block_stripped.lstrip("\n")
            if block_stripped:
                return block_stripped.strip()
        tail = segments[-1].strip()
        if tail:
            return tail

    return content
