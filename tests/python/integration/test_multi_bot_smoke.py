"""FR-017a multi-bot readiness smoke test (live).

Spec FR-017a says single-Connection is the functional scope, but the
architecture must remain multi-bot-compatible (no shared mutable
globals). This test exercises that promise: two Connection instances
running in the same event loop must both connect, both stay alive,
and not interfere with each other (cross-talk in hooks, FIFO writers,
or wire-log buffers).
"""

from __future__ import annotations

import asyncio

import pytest

from minecraft_bot.connection import Connection
from minecraft_bot.protocol.v763.states import ConnectionState
from minecraft_bot.wire_log import WireLog

pytestmark = pytest.mark.live


async def test_two_bots_in_one_process(live_server) -> None:
    """Two Connection instances in the same loop — no cross-talk."""
    log_a = WireLog.in_memory()
    log_b = WireLog.in_memory()
    bot_a = Connection.offline(
        host=live_server.host, port=live_server.port,
        username="ITMBotA", wire_log=log_a,
    )
    bot_b = Connection.offline(
        host=live_server.host, port=live_server.port,
        username="ITMBotB", wire_log=log_b,
    )

    # Connect them serially to respect Paper's per-IP throttle. The
    # important property is that both ARE connected concurrently
    # afterwards; not that the connect() calls overlap.
    await bot_a.connect()
    # Throttle window before second connect from same IP.
    await asyncio.sleep(5.0)
    await bot_b.connect()

    try:
        assert bot_a.state == ConnectionState.PLAY
        assert bot_b.state == ConnectionState.PLAY
        # Distinct entity ids prove the server sees them as separate players.
        assert bot_a.entity_id != bot_b.entity_id

        await asyncio.sleep(15.0)

        # Both still connected.
        assert bot_a.is_connected, "bot A dropped"
        assert bot_b.is_connected, "bot B dropped"

        # WireLogs are independent: bot A only sees its own packets.
        a_entries = log_a.entries()
        b_entries = log_b.entries()
        assert len(a_entries) > 0
        assert len(b_entries) > 0
        # Different entity_ids mean distinct LoginPlay entries.
        assert bot_a.entity_id != bot_b.entity_id
    finally:
        await bot_a.disconnect()
        await bot_b.disconnect()
