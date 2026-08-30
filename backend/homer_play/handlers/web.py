from __future__ import annotations

from dataclasses import dataclass

from ..bridge import BridgeClient
from ..models import WebActivityData, WebActivityRequest
from ..parsers import map_web_activity


@dataclass(frozen=True)
class HandlerResult:
    data: dict


async def run_web_activity(
    payload: WebActivityRequest,
    bridge: BridgeClient,
    *,
    request_id: str,
) -> HandlerResult:
    interpreted = map_web_activity(payload.message, payload.input.window)
    raw = await bridge.execute(
        "web.activity",
        {"window": interpreted.window, "view": interpreted.view},
        request_id=request_id,
        timeout_seconds=0.75,
    )
    data = WebActivityData.model_validate(raw)
    return HandlerResult(data.model_dump(mode="json"))
