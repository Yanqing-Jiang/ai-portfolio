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
MAX_STREAM_DURATION = 480  # 8 minutes — allows gpt-5.4 narrative to complete


async def with_heartbeat(
    gen: AsyncGenerator,
    interval: float = HEARTBEAT_INTERVAL,
    max_duration: float = MAX_STREAM_DURATION,
) -> AsyncGenerator[str, None]:
    """Wrap an async SSE generator with periodic heartbeat comments and absolute timeout.

    Uses asyncio.wait on a shielded task to avoid cancelling the upstream generator
    when the heartbeat interval elapses (asyncio.wait_for would cancel __anext__).
    """
    start = time.monotonic()
    ait = gen.__aiter__()
    pending_next: asyncio.Task | None = None
    try:
        while True:
            elapsed = time.monotonic() - start
            if elapsed >= max_duration:
                # Emit a parseable done signal so EventSource closes cleanly
                # instead of an SSE comment (which EventSource ignores → 5 retries)
                yield 'data: {"done": true, "timeout": true}\n\n'
                break

            remaining = max_duration - elapsed
            wait = min(interval, remaining)

            if pending_next is None:
                pending_next = asyncio.ensure_future(ait.__anext__())

            done, _ = await asyncio.wait({pending_next}, timeout=wait)

            if pending_next in done:
                try:
                    chunk = pending_next.result()
                except StopAsyncIteration:
                    break
                pending_next = None
                yield chunk
            else:
                # Heartbeat — task is still running, don't cancel it
                if time.monotonic() - start >= max_duration:
                    yield 'data: {"done": true, "timeout": true}\n\n'
                    break
                yield ": heartbeat\n\n"
    finally:
        if pending_next is not None and not pending_next.done():
            pending_next.cancel()
            try:
                await pending_next
            except (asyncio.CancelledError, StopAsyncIteration):
                pass
