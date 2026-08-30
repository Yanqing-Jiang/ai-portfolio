from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import ValidationError

try:
    import rate_limiter as shared_rate_limiter
except ImportError:  # pragma: no cover
    from .. import rate_limiter as shared_rate_limiter  # type: ignore

from .bridge import BridgeClient, BridgeFailure
from .handlers import run_extract, run_scheduler_query, run_search, run_web_activity
from .models import (
    ErrorResponse,
    ExecutorRouteRequest,
    MCP_ARGUMENT_MODEL_BY_TOOL,
    McpCallRequest,
    McpListRequest,
    MemoryExtractRequest,
    MemorySearchRequest,
    PlayRequest,
    RESPONSE_MODEL_BY_KEY,
    SchedulerQueryRequest,
    VoiceRequest,
    WebActivityRequest,
)
from .parsers import parse_scheduler_query
from .rate_limit import RateLimitResult, enforce_hourly_limit, reset_at_iso
from .replays import get_replay
from .spend import (
    RESERVATION_MICROS,
    SpendLedger,
    SpendReservation,
    daily_cap_micro,
    estimate_gemini_micro,
    micro_to_usd,
)


logger = logging.getLogger(__name__)

BODY_LIMIT_BYTES = 8 * 1024
PUBLIC_MCP_TOOLS = frozenset({"memory_search", "public_schedule_status", "public_runtime_status"})
VOICE_UNSAFE_RE = re.compile(
    r"(?:https?://|www\.|[\w.+-]+@[\w.-]+\.[a-z]{2,}|\+?\d[\d\s().-]{7,}\d|"
    r"</?[a-z][^>]*>|\b(?:ssn|social security|credit card|impersonate|authenticate|authorize payment)\b)",
    re.IGNORECASE,
)


def _request_id(request: Request) -> str:
    existing = request.headers.get("x-request-id", "")
    try:
        return str(uuid.UUID(existing))
    except (ValueError, AttributeError):
        return str(uuid.uuid4())


def _error_response(
    request_id: str,
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool,
    fields: dict[str, str] | None = None,
    limits: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    raw: dict[str, Any] = {
        "ok": False,
        "request_id": request_id,
        "error": {"code": code, "message": message, "retryable": retryable, "fields": fields},
        "limits": limits,
    }
    validated = ErrorResponse.model_validate(raw)
    response_headers = {
        "Cache-Control": "no-store, private",
        "X-Content-Type-Options": "nosniff",
        "X-Request-Id": request_id,
    }
    response_headers.update(headers or {})
    return JSONResponse(
        status_code=status_code,
        content=validated.model_dump(mode="json", exclude_none=True),
        headers=response_headers,
    )


def _validation_fields(exc: RequestValidationError) -> dict[str, str]:
    fields: dict[str, str] = {}
    for error in exc.errors()[:8]:
        location = ".".join(str(item) for item in error.get("loc", ()) if item != "body") or "body"
        error_type = str(error.get("type", "invalid"))
        if error_type == "extra_forbidden":
            explanation = "unknown field"
        elif error_type in {"string_too_long", "less_than_equal"}:
            explanation = "value exceeds the public limit"
        elif error_type in {"string_too_short", "greater_than_equal"}:
            explanation = "value is below the public minimum"
        else:
            explanation = "invalid value"
        fields[location] = explanation
    return fields


class HomerPlayRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def guarded(request: Request):
            request_id = _request_id(request)
            request.state.homer_play_request_id = request_id
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > BODY_LIMIT_BYTES:
                        return _error_response(
                            request_id,
                            status_code=413,
                            code="payload_too_large",
                            message="Request body exceeds the 8 KiB public limit.",
                            retryable=False,
                            fields={"body": "maximum 8192 bytes"},
                        )
                except ValueError:
                    pass
            body = await request.body()
            if len(body) > BODY_LIMIT_BYTES:
                return _error_response(
                    request_id,
                    status_code=413,
                    code="payload_too_large",
                    message="Request body exceeds the 8 KiB public limit.",
                    retryable=False,
                    fields={"body": "maximum 8192 bytes"},
                )
            try:
                response = await original(request)
            except RequestValidationError as exc:
                response = _error_response(
                    request_id,
                    status_code=400,
                    code="invalid_request",
                    message="The request does not match the public Homer play contract.",
                    retryable=False,
                    fields=_validation_fields(exc),
                )
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Request-Id"] = request_id
            return response

        return guarded


router = APIRouter(prefix="/api/homer", tags=["homer-play"], route_class=HomerPlayRoute)
bridge_client = BridgeClient()
spend_ledger = SpendLedger(shared_rate_limiter.redis_pool)


def _limits(rate: RateLimitResult) -> dict[str, Any]:
    return {
        "remaining_this_hour": rate.remaining,
        "reset_at": reset_at_iso(rate.reset_epoch),
    }


def _spend(reserved_micro: int = 0, charged_micro: int = 0) -> dict[str, float]:
    return {
        "reserved_usd": micro_to_usd(reserved_micro),
        "charged_usd": micro_to_usd(charged_micro),
        "daily_cap_usd": micro_to_usd(daily_cap_micro()),
    }


def _success_response(
    payload: PlayRequest,
    request_id: str,
    rate: RateLimitResult,
    *,
    data: dict[str, Any],
    reply: str,
    source: str,
    reserved_micro: int,
    charged_micro: int,
) -> JSONResponse:
    key = f"{payload.tab}.{payload.action}"
    raw = {
        "ok": True,
        "version": "1",
        "request_id": request_id,
        "tab": payload.tab,
        "action": payload.action,
        "mode": "live",
        "reply": reply,
        "data": data,
        "receipt": {
            "source": source,
            "observed_at": datetime.now(timezone.utc),
            "read_only": True,
            "persisted": False,
        },
        "limits": _limits(rate),
        "spend": _spend(reserved_micro, charged_micro),
        "degraded": None,
    }
    validated = RESPONSE_MODEL_BY_KEY[key].model_validate(raw)
    return JSONResponse(content=validated.model_dump(mode="json", by_alias=True))


def _degraded_response(
    payload: PlayRequest,
    request_id: str,
    rate: RateLimitResult,
    *,
    reason: str,
    reserved_micro: int = 0,
    charged_micro: int = 0,
) -> JSONResponse:
    try:
        raw = get_replay(payload.tab, payload.action)
    except KeyError:
        return _error_response(
            request_id,
            status_code=503,
            code="service_unavailable",
            message="This Homer play action is temporarily unavailable.",
            retryable=True,
            limits=_limits(rate),
        )
    raw["request_id"] = request_id
    raw["mode"] = "degraded"
    raw["limits"] = _limits(rate)
    raw["spend"] = _spend(reserved_micro, charged_micro)
    raw["degraded"]["reason"] = reason
    validated = RESPONSE_MODEL_BY_KEY[f"{payload.tab}.{payload.action}"].model_validate(raw)
    return JSONResponse(content=validated.model_dump(mode="json", by_alias=True))


def _validate_mcp_call(payload: McpCallRequest, request_id: str) -> JSONResponse | None:
    if payload.input.tool not in PUBLIC_MCP_TOOLS:
        return _error_response(
            request_id,
            status_code=403,
            code="tool_not_allowed",
            message="That tool is not part of the public read-only MCP facade.",
            retryable=False,
            fields={"input.tool": "not in public allowlist"},
        )
    try:
        MCP_ARGUMENT_MODEL_BY_TOOL[payload.input.tool].model_validate(payload.input.arguments)
    except ValidationError as exc:
        return _error_response(
            request_id,
            status_code=400,
            code="invalid_request",
            message="Tool arguments do not match the public schema.",
            retryable=False,
            fields={
                "input.arguments." + ".".join(str(item) for item in error.get("loc", ())): "invalid value"
                for error in exc.errors()[:8]
            },
        )
    return None


def _validate_voice(payload: VoiceRequest, request_id: str) -> JSONResponse | None:
    if "\n" in payload.message or "\r" in payload.message or VOICE_UNSAFE_RE.search(payload.message):
        return _error_response(
            request_id,
            status_code=400,
            code="unsafe_voice_text",
            message="Voice text must be a short, single-line public-safe phrase without contact, payment, markup, or impersonation content.",
            retryable=False,
            fields={"message": "unsafe voice text"},
        )
    return None


async def _reserve(payload: PlayRequest, request_id: str) -> SpendReservation:
    return await spend_ledger.reserve(f"{payload.tab}.{payload.action}", request_id)


def _reservation_failure(
    payload: PlayRequest,
    request_id: str,
    rate: RateLimitResult,
    reservation: SpendReservation,
) -> JSONResponse:
    if reservation.reason == "reservation_conflict":
        return _error_response(
            request_id,
            status_code=400,
            code="invalid_request",
            message="The request ID was already used for a different Homer play action.",
            retryable=False,
            limits=_limits(rate),
        )
    return _degraded_response(
        payload, request_id, rate, reason=reservation.reason or "daily_spend_cap"
    )


@router.post("/play")
async def homer_play(payload: PlayRequest, request: Request):
    request_id = request.state.homer_play_request_id

    if isinstance(payload, McpCallRequest):
        invalid = _validate_mcp_call(payload, request_id)
        if invalid is not None:
            return invalid
    if isinstance(payload, VoiceRequest):
        invalid = _validate_voice(payload, request_id)
        if invalid is not None:
            return invalid

    rate = await enforce_hourly_limit(request)
    if not rate.allowed:
        return _error_response(
            request_id,
            status_code=429,
            code="rate_limited",
            message="Too many Homer play requests from this IP. Try again after the hourly window resets.",
            retryable=True,
            limits=_limits(rate),
            headers={"Retry-After": str(rate.retry_after)},
        )

    if isinstance(payload, (ExecutorRouteRequest, McpListRequest, McpCallRequest, VoiceRequest)):
        return _degraded_response(payload, request_id, rate, reason="not_yet_enabled")

    if os.getenv("ENVIRONMENT", "development").lower() == "production" and not rate.redis_available:
        return _degraded_response(payload, request_id, rate, reason="rate_backend_unavailable")

    if isinstance(payload, MemorySearchRequest):
        reservation = await _reserve(payload, request_id)
        if not reservation.allowed:
            return _reservation_failure(payload, request_id, rate, reservation)
        try:
            result = await run_search(payload)
            charged = await spend_ledger.finalize(reservation, result.charged_micro_usd)
            return _success_response(
                payload,
                request_id,
                rate,
                data=result.data,
                reply=f"Found {len(result.data['results'])} matching public memory claims.",
                source="public_corpus",
                reserved_micro=reservation.reserved_micro_usd,
                charged_micro=charged,
            )
        except Exception as exc:
            logger.warning("Homer play memory search failed request_id=%s error=%s", request_id, type(exc).__name__)
            charged = await spend_ledger.finalize(reservation, None)
            return _degraded_response(
                payload, request_id, rate, reason="provider_unavailable",
                reserved_micro=reservation.reserved_micro_usd, charged_micro=charged,
            )

    if isinstance(payload, MemoryExtractRequest):
        reservation = await _reserve(payload, request_id)
        if not reservation.allowed:
            return _reservation_failure(payload, request_id, rate, reservation)
        try:
            result = await run_extract(payload, bridge_client, request_id=request_id)
            charged = await spend_ledger.finalize(reservation, result.charged_micro_usd)
            return _success_response(
                payload,
                request_id,
                rate,
                data=result.data,
                reply=f"Dry run extracted {len(result.data['candidates'])} ephemeral candidate(s); no writes were attempted.",
                source="live_bridge",
                reserved_micro=reservation.reserved_micro_usd,
                charged_micro=charged,
            )
        except BridgeFailure as exc:
            charged = await spend_ledger.finalize(reservation, None if exc.reason == "live_timeout" else 0)
            return _degraded_response(
                payload, request_id, rate, reason=exc.reason,
                reserved_micro=reservation.reserved_micro_usd, charged_micro=charged,
            )
        except (ValidationError, ValueError):
            charged = await spend_ledger.finalize(reservation, None)
            return _degraded_response(
                payload, request_id, rate, reason="bridge_unavailable",
                reserved_micro=reservation.reserved_micro_usd, charged_micro=charged,
            )

    if isinstance(payload, SchedulerQueryRequest):
        reservation = await _reserve(payload, request_id)
        if not reservation.allowed:
            return _reservation_failure(payload, request_id, rate, reservation)
        parsed = await parse_scheduler_query(payload.message)
        if parsed.provider_attempted and parsed.used_fallback:
            parser_cost: int | None = None
        elif parsed.provider_attempted and parsed.usage_reported:
            parser_cost = estimate_gemini_micro(
                parsed.input_tokens, parsed.output_tokens, reservation.reserved_micro_usd
            )
        elif parsed.provider_attempted:
            parser_cost = None
        else:
            parser_cost = 0
        charged = await spend_ledger.finalize(reservation, parser_cost)
        try:
            result = await run_scheduler_query(payload, parsed, bridge_client, request_id=request_id)
            return _success_response(
                payload,
                request_id,
                rate,
                data=result.data,
                reply=f"Found {len(result.data['jobs'])} public scheduler job(s) for the interpreted filters.",
                source="live_bridge",
                reserved_micro=reservation.reserved_micro_usd,
                charged_micro=charged,
            )
        except BridgeFailure as exc:
            return _degraded_response(
                payload, request_id, rate, reason=exc.reason,
                reserved_micro=reservation.reserved_micro_usd, charged_micro=charged,
            )
        except (ValidationError, ValueError):
            return _degraded_response(
                payload, request_id, rate, reason="bridge_unavailable",
                reserved_micro=reservation.reserved_micro_usd, charged_micro=charged,
            )

    if isinstance(payload, WebActivityRequest):
        try:
            result = await run_web_activity(payload, bridge_client, request_id=request_id)
            return _success_response(
                payload,
                request_id,
                rate,
                data=result.data,
                reply=f"Here is sanitized aggregate Homer activity for the last {result.data['window']}.",
                source="live_bridge",
                reserved_micro=0,
                charged_micro=0,
            )
        except BridgeFailure as exc:
            return _degraded_response(payload, request_id, rate, reason=exc.reason)
        except (ValidationError, ValueError):
            return _degraded_response(payload, request_id, rate, reason="bridge_unavailable")

    # The discriminated union makes this unreachable, but retaining an explicit
    # safe error keeps the route closed if a future type is added without dispatch.
    return _error_response(
        request_id,
        status_code=400,
        code="invalid_request",
        message="Unsupported Homer play action.",
        retryable=False,
        limits=_limits(rate),
    )
