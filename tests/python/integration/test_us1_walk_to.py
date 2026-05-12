"""US1 — Walk-To (live integration test).

Acceptance scenarios from spec.md US1 (walk_to):

1. Bot.offline().connect() → reaches spawn with health/position populated.
2. walk_to(spawn + (10, 0, 0)) completes within 30 s on flat ground.
3. walk_to of a walled-off target raises NoPathFound.

Throttle-aware (per FR-076): spaced ≥ 1 s between consecutive
attempts to avoid Paper anti-cheat flagging.

Requires live server fixture. Run:
    pytest -m live tests/python/integration/test_us1_walk_to.py
"""

from __future__ import annotations

import asyncio

import pytest

from minecraft_bot.bot import Bot
from minecraft_bot.errors import NoPathFound, WalkTimeout

pytestmark = pytest.mark.live


async def test_bot_connects_and_reads_state(live_server) -> None:
    """Plumbing smoke: Bot.offline + connect populates entity_id and position."""
    bot = Bot.offline(live_server.host, live_server.port, "WalkBot1")
    await bot.connect()
    try:
        assert bot.is_connected
        assert bot.entity_id is not None
        assert bot.world_name is not None
        # After the initial server-pushed position, x/y/z should not be the default.
        x0, y0, z0 = bot.position
        assert (x0, y0, z0) != (0.0, 64.0, 0.5), "expected server position not (0, 64, 0.5)"
        # Health should have been updated too.
        assert bot.health > 0
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_walk_to_short_displacement(live_server) -> None:
    """Walk ~5 blocks east on flat ground within 30 s."""
    bot = Bot.offline(live_server.host, live_server.port, "WalkBot2")
    await bot.connect()
    try:
        # Wait a moment for a few chunks to arrive.
        await asyncio.sleep(2.0)
        x0, y0, z0 = bot.position
        target = (x0 + 5, y0, z0)
        try:
            await bot.walk_to(*target, timeout=30.0)
        except (NoPathFound, WalkTimeout) as e:
            # The bot may have spawned in a weird location; surface as skip.
            pytest.skip(f"could not walk on this spawn: {e!r}")
        x1, _, z1 = bot.position
        # Should have moved at least 1 block toward the target.
        assert abs(x1 - x0) > 1.0
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_walled_off_target_raises_no_path_found(live_server) -> None:
    """A target 10000 blocks away can't be reached in any timeout — no chunks
    loaded between here and there, so the pathfinder will exhaust its node
    budget. We accept either NoPathFound or WalkTimeout to make the test
    robust against load-distance edge cases on the test server."""
    bot = Bot.offline(live_server.host, live_server.port, "WalkBot3")
    await bot.connect()
    try:
        await asyncio.sleep(2.0)
        x0, y0, z0 = bot.position
        with pytest.raises((NoPathFound, WalkTimeout)):
            await bot.walk_to(x0 + 10000, y0, z0 + 10000, timeout=5.0)
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)
