"""T015 — WireLog capture fixture for parity tests.

Wraps a backend-agnostic `run_method_under_capture(backend, async_call)`
that connects a bot, attaches an in-memory WireLog sink, runs the
provided coroutine, disconnects, and returns the captured packet
sequence as a list of `{kind, payload, tick}` dicts ready for
`_parity_normalizer.normalize_trace`.

The fixture intentionally accepts either backend via duck typing —
both `minecraft_bot.Bot` and `minecraft_bot_accel.Bot` expose a
`wire_log` attribute on the underlying Connection.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from minecraft_bot.protocol.v763.states import Direction
from minecraft_bot.wire_log import InMemory, WireLog, WireLogEntry


async def run_method_under_capture(
    bot: Any,
    method_call: Callable[[Any], Awaitable[Any]],
    *,
    direction_filter: Direction | None = Direction.SERVERBOUND,
) -> list[dict[str, Any]]:
    """Run `method_call(bot)` while capturing the WireLog.

    `direction_filter` defaults to serverbound — that is what parity
    cares about (what bytes the client *sends*). Pass `None` to keep
    both directions.

    The bot is assumed to be already connected. The fixture attaches a
    fresh `InMemory` sink to the connection's WireLog, runs the
    method, and detaches.
    """
    sink = InMemory(capacity=1024)
    wire_log = _attach_sink(bot, sink)
    try:
        await method_call(bot)
    finally:
        _detach_sink(bot, wire_log)

    return [
        _entry_to_dict(e)
        for e in sink.entries()
        if direction_filter is None or e.direction == direction_filter
    ]


def _attach_sink(bot: Any, sink: InMemory) -> WireLog:
    """Best-effort attach: works on both python-ref Bot and accel Bot."""
    conn = _get_connection(bot)
    existing = getattr(conn, "wire_log", None)
    if existing is None:
        wire_log = WireLog(sinks=[sink])
        # python-ref Connection stores wire_log on init only; for an
        # already-running connection we patch the attribute and the
        # dispatcher picks up new entries on the next packet.
        conn._wire_log = wire_log
        return wire_log
    # WireLog supports multiple sinks — add ours alongside existing
    # ones (e.g. a JsonlFile capture).
    existing._sinks.append(sink)
    return existing


def _detach_sink(bot: Any, wire_log: WireLog) -> None:
    conn = _get_connection(bot)
    sinks = getattr(wire_log, "_sinks", None)
    if sinks:
        sinks[:] = [s for s in sinks if not isinstance(s, InMemory)]
    # If we created the WireLog from scratch (no existing one before
    # attach), null it out so subsequent calls don't leak the sink.
    if not getattr(wire_log, "_sinks", None):
        conn._wire_log = None


def _get_connection(bot: Any) -> Any:
    """Pull the Connection out of either backend's Bot."""
    if hasattr(bot, "_conn"):
        return bot._conn
    if hasattr(bot, "connection"):
        return bot.connection
    raise AttributeError("bot has no `_conn`/`connection` attribute")


def _entry_to_dict(entry: WireLogEntry) -> dict[str, Any]:
    """Map a WireLogEntry into the normalizer's expected shape."""
    return {
        "kind": entry.name or f"id_{entry.packet_id}",
        "payload": dict(entry.fields) if entry.fields else {},
        # `tick` is best-effort: the entry's timestamp is seconds since
        # session start, multiplied by 20 to get game ticks. Used only
        # by the Q4 whitelist; non-tolerant comparisons ignore it.
        "tick": int(entry.ts * 20.0),
    }


__all__ = ["run_method_under_capture"]
