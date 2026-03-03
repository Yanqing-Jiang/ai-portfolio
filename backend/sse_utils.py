"""SSE heartbeat wrapper for Cloudflare Tunnel compatibility.

CF Tunnel (Free plan) has a 100-second idle timeout on streaming connections.
This wrapper sends SSE comments (`: heartbeat`) every 20s when the upstream
generator is idle, keeping the connection alive without affecting EventSource
clients (which ignore SSE comments per spec).
"""

import asyncio
import time
from typing import AsyncGenerator

HEARTBEAT_INTERVAL = 20  # seconds — well under CF's 100s timeout
MAX_STREAM_DURATION = 300  # 5 minutes absolute max per connection


async def with_heartbeat(
    gen: AsyncGenerator,
    interval: float = HEARTBEAT_INTERVAL,
    max_duration: float = MAX_STREAM_DURATION,
) -> AsyncGenerator[str, None]:
    """Wrap an async SSE generator with periodic heartbeat comments and absolute timeout."""
    start = time.monotonic()
    ait = gen.__aiter__()
    while True:
        elapsed = time.monotonic() - start
        if elapsed >= max_duration:
            yield ": timeout\n\n"
            break
        try:
            remaining = max_duration - elapsed
            wait = min(interval, remaining)
            chunk = await asyncio.wait_for(ait.__anext__(), timeout=wait)
            yield chunk
        except asyncio.TimeoutError:
            if time.monotonic() - start >= max_duration:
                yield ": timeout\n\n"
                break
            yield ": heartbeat\n\n"
        except StopAsyncIteration:
            break
