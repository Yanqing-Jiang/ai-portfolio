from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

try:
    from gemini_service import _ensure_client, genai_types
except ImportError:  # pragma: no cover
    from ..gemini_service import _ensure_client, genai_types  # type: ignore

from .models import InterpretedQuery
from .spend import estimate_tokens


DEFAULT_FLASH_MODEL = "gemini-2.5-flash-lite"


@dataclass(frozen=True)
class SchedulerParseResult:
    query: InterpretedQuery
    input_tokens: int
    output_tokens: int
    provider_attempted: bool
    used_fallback: bool
    usage_reported: bool = False


def keyword_scheduler_parser(message: str) -> InterpretedQuery:
    lowered = message.lower()
    if re.search(r"\b(fail(?:ed|ure|ures|ing)?|error(?:s|ed)?)\b", lowered):
        status = "failed"
    elif re.search(r"\b(running|in progress|active now)\b", lowered):
        status = "running"
    elif re.search(r"\b(success(?:ful|es)?|succeeded|completed?)\b", lowered):
        status = "success"
    else:
        status = "all"

    if re.search(r"\b(week|weekly|7d|seven days?)\b", lowered):
        since_hours = 168
    elif re.search(r"\b(hour|hourly|1h|sixty minutes?)\b", lowered):
        since_hours = 1
    else:
        since_hours = 24

    include_next = bool(re.search(r"\b(next|upcoming|when.*run|schedule[ds]?)\b", lowered))
    # Only treat explicitly backticked kebab-case names as job IDs. This avoids
    # guessing from prose; the bridge still applies its default-deny job allowlist.
    job_ids = [
        match.group(1).lower()
        for match in re.finditer(r"`([a-z0-9][a-z0-9-]{0,63})`", message, flags=re.IGNORECASE)
    ]
    return InterpretedQuery(
        status=status,
        since_hours=since_hours,
        job_ids=list(dict.fromkeys(job_ids))[:8],
        include_next_run=include_next,
    )


def _response_text(response: Any) -> str:
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        if isinstance(parsed, InterpretedQuery):
            return parsed.model_dump_json()
        if isinstance(parsed, dict):
            return json.dumps(parsed)
    text = getattr(response, "text", None)
    return text if isinstance(text, str) else ""


def _usage(response: Any, message: str, output_text: str) -> tuple[int, int, bool]:
    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", None)
    output_tokens = getattr(usage, "candidates_token_count", None)
    reported = isinstance(input_tokens, int) and isinstance(output_tokens, int)
    return (
        int(input_tokens) if isinstance(input_tokens, int) else estimate_tokens(message),
        int(output_tokens) if isinstance(output_tokens, int) else estimate_tokens(output_text),
        reported,
    )


def _call_gemini(message: str) -> tuple[InterpretedQuery, int, int, bool]:
    if genai_types is None:
        raise RuntimeError("google-genai types unavailable")
    client = _ensure_client()
    model = os.getenv("HOMER_PLAY_FLASH_MODEL", DEFAULT_FLASH_MODEL)
    prompt = (
        "Classify this scheduler question into exactly the supplied JSON schema. "
        "status is all, success, failed, or running. since_hours is exactly 1, 24, or 168. "
        "Only copy a job_ids value when the visitor explicitly names a lowercase kebab-case job ID. "
        "include_next_run is true only when next/upcoming timing is requested. No SQL and no extra fields.\n\n"
        f"Visitor question:\n{message}"
    )
    config = genai_types.GenerateContentConfig(
        temperature=0,
        max_output_tokens=128,
        response_mime_type="application/json",
        response_schema=InterpretedQuery,
    )
    # No tool configuration is supplied; this is a direct structured-output call.
    response = client.models.generate_content(model=model, contents=prompt, config=config)
    output_text = _response_text(response)
    parsed = InterpretedQuery.model_validate_json(output_text)
    input_tokens, output_tokens, usage_reported = _usage(response, prompt, output_text)
    return parsed, input_tokens, output_tokens, usage_reported


async def parse_scheduler_query(message: str) -> SchedulerParseResult:
    if not os.getenv("GEMINI_API_KEY"):
        fallback = keyword_scheduler_parser(message)
        return SchedulerParseResult(fallback, 0, 0, False, True)
    try:
        parsed, input_tokens, output_tokens, usage_reported = await asyncio.to_thread(_call_gemini, message)
        # Re-validation is intentional: provider output is never trusted.
        parsed = InterpretedQuery.model_validate(parsed.model_dump())
        return SchedulerParseResult(parsed, input_tokens, output_tokens, True, False, usage_reported)
    except (Exception, ValidationError):
        fallback = keyword_scheduler_parser(message)
        return SchedulerParseResult(fallback, 0, 0, True, True)


@dataclass(frozen=True)
class WebQuery:
    window: str
    view: str


def map_web_activity(message: str, requested_window: str) -> WebQuery:
    lowered = message.lower()
    if re.search(r"\b(week|weekly|7d|seven days?)\b", lowered):
        window = "7d"
    elif re.search(r"\b(last hour|past hour|1h|hourly)\b", lowered):
        window = "1h"
    elif re.search(r"\b(today|24h|day|daily)\b", lowered):
        window = "24h"
    else:
        window = requested_window

    if re.search(r"\b(thread|threads|conversation|messages?)\b", lowered):
        view = "threads"
    elif re.search(r"\b(run|runs|job|jobs|schedule|failed|completed)\b", lowered):
        view = "runs"
    elif re.search(r"\b(event|events|tool|tools)\b", lowered):
        view = "events"
    else:
        view = "overview"
    return WebQuery(window=window, view=view)
