"""LLM adapter utilities for the analytics agent runtime."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Awaitable, Callable, Dict, List, Optional

from unified_responses_client import get_unified_client

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = os.getenv("OPENAI_RESPONSES_AGENT_MODEL") or os.getenv("OPENAI_MODEL", "gpt-5-mini-2025-08-07")

_GUIDANCE_TEMPLATE = (
    "You are the analytics single-agent orchestrator."
    " Available tools (call by returning type=\"tool\" with the payload schema):\n"
    "{tool_catalog}\n"
    "When you want to answer the user, return type=\"message\" and content with the reply."
    " Respond strictly with JSON containing keys: type (message|tool|error), content, tool, observation, message."
    " If a tool call fails and you cannot continue, return type=\"error\" with message."
)


def build_responses_llm_adapter(
    *,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
) -> Callable[[List[Dict[str, str]], Dict[str, Any]], Awaitable[Dict[str, Any]]]:
    """Return an adapter that uses the unified Responses client."""

    resolved_model = model or _DEFAULT_MODEL
    client = get_unified_client()

    async def _adapter(history: List[Dict[str, str]], tool_specs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        instructions = _build_guidance(tool_specs)
        messages = _format_history_with_guidance(history, instructions)
        params: Dict[str, Any] = {
            "model": resolved_model,
            "input": messages,
        }
        if reasoning_effort:
            params["reasoning"] = {"effort": reasoning_effort}
        logger.debug(
            "Dispatching agent LLM request",
            extra={"model": resolved_model, "history_len": len(history), "tools": list(tool_specs.keys())},
        )
        response = await client.client.responses.create(**params)
        response_dict = client._as_dict(response) or {}
        content = client._extract_output_text(response)  # type: ignore[attr-defined]
        if not content:
            raise RuntimeError("LLM returned empty response content")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("Agent LLM response is not valid JSON: %s", content)
            raise RuntimeError("LLM response parsing failed") from exc
        metadata = {"response_id": response_dict.get("id"), "usage": response_dict.get("usage")}
        if isinstance(parsed.get("_metadata"), dict):
            parsed["_metadata"].update({k: v for k, v in metadata.items() if v is not None})
        else:
            parsed["_metadata"] = metadata
        return parsed

    return _adapter


def _build_guidance(tool_specs: Dict[str, Dict[str, Any]]) -> str:
    lines = []
    for name, meta in tool_specs.items():
        lines.append(f"- {name}: {meta.get('description', 'No description available')}")
    catalog = "\n".join(lines) if lines else "- (no tools registered)"
    return _GUIDANCE_TEMPLATE.format(tool_catalog=catalog)


def _format_history_with_guidance(
    history: List[Dict[str, str]],
    instructions: str,
) -> List[Dict[str, Any]]:
    formatted: List[Dict[str, Any]] = []
    injected_guidance = False
    for entry in history:
        role = entry.get("role") or "user"
        content = entry.get("content") or ""
        formatted.append(
            {
                "role": role,
                "content": [{"type": "input_text", "text": content}],
            }
        )
        if role == "system" and not injected_guidance:
            formatted.append(
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": instructions}],
                }
            )
            injected_guidance = True
    if not injected_guidance:
        formatted.insert(
            0,
            {"role": "system", "content": [{"type": "input_text", "text": instructions}]},
        )
    return formatted



