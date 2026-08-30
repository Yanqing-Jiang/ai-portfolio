from __future__ import annotations

import hashlib
import hmac
import logging
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal

import httpx


BridgeCommand = Literal["memory.extract_dry_run", "scheduler.query", "web.activity", "todo.summary"]


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BridgeFailure(Exception):
    reason: Literal["bridge_unavailable", "live_timeout"]


class BridgeClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        secret: str | None = None,
        client: httpx.AsyncClient | None = None,
        clock=time.time,
    ) -> None:
        self.base_url = (base_url or os.getenv("HOMER_PUBLIC_BRIDGE_URL", "http://host.docker.internal:3012")).rstrip("/")
        self.secret = secret if secret is not None else os.getenv("HOMER_PUBLIC_BRIDGE_SECRET", "")
        self.client = client
        self.clock = clock

    async def execute(
        self,
        command: BridgeCommand,
        input_data: dict[str, Any],
        *,
        request_id: str | None = None,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        if not self.secret:
            raise BridgeFailure("bridge_unavailable")

        request_id = request_id or str(uuid.uuid4())
        timestamp = str(int(self.clock()))
        payload = {"command": command, "input": input_data}
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        signature_payload = timestamp.encode() + b"." + request_id.encode() + b"." + body
        signature = hmac.new(self.secret.encode("utf-8"), signature_payload, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Homer-Bridge-Timestamp": timestamp,
            "X-Homer-Bridge-Request-Id": request_id,
            "X-Homer-Bridge-Signature": signature,
        }
        url = f"{self.base_url}/v1/public/execute"

        try:
            if self.client is not None:
                response = await self.client.post(url, content=body, headers=headers, timeout=timeout_seconds)
            else:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    response = await client.post(url, content=body, headers=headers)
            response.raise_for_status()
            if len(response.content) > 64 * 1024:
                raise BridgeFailure("bridge_unavailable")
            envelope = response.json()
            if not isinstance(envelope, dict):
                raise BridgeFailure("bridge_unavailable")
            # The bridge wraps every reply as {ok, request_id, command, data} or
            # {ok:false, error:{code,...}}. Handlers only ever see `data`.
            if envelope.get("ok") is False or "data" not in envelope:
                err = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
                logger.warning("Homer bridge returned an error envelope: code=%s message=%s", err.get("code") or "unknown", err.get("message") or "")
                raise BridgeFailure("bridge_unavailable")
            data = envelope["data"]
            if not isinstance(data, dict):
                raise BridgeFailure("bridge_unavailable")
            return data
        except BridgeFailure:
            raise
        except httpx.TimeoutException as exc:
            raise BridgeFailure("live_timeout") from exc
        except httpx.HTTPStatusError as exc:
            logger.warning("Homer bridge HTTP %s: %s", exc.response.status_code, exc.response.text[:300])
            raise BridgeFailure("bridge_unavailable") from exc
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Homer bridge transport failure: %s", type(exc).__name__)
            raise BridgeFailure("bridge_unavailable") from exc
