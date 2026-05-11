"""Synthetic narrative heartbeat for the fortune stream.

PR2 of the latency refactor dropped ``summary="auto"`` from the narrative
agent's model settings — the model used to ship periodic reasoning summaries
that the ThinkingPanel rendered as "Still thinking…" breadcrumbs, but those
summaries cost real TTFB (~3-8s upfront) and bloat reasoning tokens.

PR5 replaces that lost UX signal with a *synthetic* heartbeat: while
``stream_result.stream_events()`` is open we emit a progress event every
``interval`` seconds (default 8s) so the panel keeps animating during the
otherwise-silent window between the last tool call and ``ResponseCompleted``.

Why a custom multiplexer rather than ``sse_utils.with_heartbeat``:

- ``with_heartbeat`` operates on the *outbound* SSE generator and yields
  raw SSE comments (``: heartbeat\\n\\n``). Comments are invisible to the
  ThinkingPanel because EventSource ignores them per spec.
- We need to inject a *typed* event into the consumer loop so it can call
  ``bridge.emit_progress`` and produce a payloaded ``data:`` line that the
  frontend's data-model patcher actually renders.

Wire shape: callers consume a single async iterator that yields either
the raw SDK ``StreamEvent`` or a ``HeartbeatTick(elapsed_s=...)`` sentinel.
The consumer branches with ``isinstance``.

Cancellation: identical to ``with_heartbeat`` — uses ``asyncio.wait`` (NOT
``asyncio.wait_for``) so an interval expiring never cancels the upstream
``__anext__`` task. On ``finally`` we cancel the pending future; awaiting
it eats the ``CancelledError``/``StopAsyncIteration`` so propagation stays
clean.

Cost: zero Postgres roundtrips. The consumer in ``routes.py`` issues
``_emit(bridge.emit_progress(...))`` *without* ``event_name="progress"``,
which keeps the emit out of the ``DURABLE_EVENTS`` mirror. The local seq
pool already comes from PR1's batched ``allocate_seq`` (chunks of 16), so
~6 heartbeats over a 50s narrative fit comfortably inside one prefetch.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator


@dataclass(frozen=True)
class HeartbeatTick:
    """Synthetic marker yielded between real SDK stream events.

    ``elapsed_s`` is monotonic seconds since the helper started — handy for
    the consumer to format the progress message ("Still reasoning… 16s") or
    to throttle further work.
    """

    elapsed_s: int


async def iter_with_heartbeats(
    upstream: AsyncIterator[Any],
    *,
    interval: float = 8.0,
) -> AsyncIterator[Any]:
    """Yield items from ``upstream`` plus a ``HeartbeatTick`` every ``interval`` s.

    The first tick fires after one full ``interval`` of silence — never at
    t=0, so the consumer doesn't double-emit a "Reasoning…" progress event
    immediately after the explicit "Generating interpretation…" signal that
    routes.py already sends before this helper is reached.

    On upstream ``StopAsyncIteration`` the generator returns cleanly. On
    cancellation (consumer breaks out, route disconnects) the pending
    ``__anext__`` future is cancelled in ``finally`` and awaited so we
    don't leak a "task was destroyed but it is pending" warning.

    ``interval`` must be strictly positive. ``asyncio.wait`` treats
    ``timeout=0`` as "poll once and return immediately", which would
    create a busy synthetic-tick loop while upstream is silent and burn
    CPU + log spam. ``interval < 0`` is rejected by ``asyncio.wait``
    anyway, but we surface a clearer error early.
    """

    if interval <= 0:
        raise ValueError(
            f"iter_with_heartbeats requires a positive interval, got {interval!r}"
        )

    start = time.monotonic()
    pending: asyncio.Future | None = None
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(upstream.__anext__())

            done, _ = await asyncio.wait({pending}, timeout=interval)

            if pending in done:
                try:
                    item = pending.result()
                except StopAsyncIteration:
                    return
                pending = None
                yield item
            else:
                # Interval expired with no upstream item — synthesize a
                # heartbeat and keep ``pending`` in flight for the next round.
                elapsed = int(time.monotonic() - start)
                yield HeartbeatTick(elapsed_s=elapsed)
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            try:
                await pending
            except (asyncio.CancelledError, StopAsyncIteration):
                pass
            except Exception:  # pragma: no cover - upstream cleanup error
                pass
