"""US1 — Walk-To (live integration test).

Acceptance scenarios from spec.md US1:

1. Bot.offline().connect() → reaches spawn with health/position populated.
2. walk_to(target) on a flat arena completes within 30 s.
3. walk_to of a walled-off / off-arena target raises NoPathFound.

The flat 61×61 stone arena lives at center (10000, 200, 10000) on the
test server. Every test teleports its bot onto the arena before
testing so the spawn terrain doesn't influence results.

Requires the live server fixture. Run:
    pytest -m live tests/python/integration/test_us1_walk_to.py
"""

from __future__ import annotations

import asyncio

import pytest

from minecraft_bot.bot import Bot
from minecraft_bot.errors import NoPathFound, WalkTimeout

pytestmark = pytest.mark.live


ARENA_CX = 10000
ARENA_CY = 200
ARENA_CZ = 10000


async def _spawn_on_arena(bot: Bot, name: str) -> None:
    """Connect a bot, teleport it onto the arena, wait for chunks."""
    await bot.connect()
    await asyncio.sleep(1.5)
    await bot.command(f"tp {name} {ARENA_CX} {ARENA_CY} {ARENA_CZ}")
    await asyncio.sleep(3.0)
    # Sanity: we should be roughly on the platform.
    assert abs(bot.x - ARENA_CX) < 2.0, f"tp failed: x={bot.x}"
    assert abs(bot.z - ARENA_CZ) < 2.0, f"tp failed: z={bot.z}"
    assert abs(bot.y - ARENA_CY) < 2.0, f"tp failed: y={bot.y}"


async def test_bot_connects_and_reads_state(live_server) -> None:
    """Plumbing smoke: Bot.offline + connect populates entity_id and position."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot")
    await bot.connect()
    try:
        assert bot.is_connected
        assert bot.entity_id is not None
        assert bot.world_name is not None
        assert bot.health > 0
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_walk_to_straight_east_on_arena(live_server) -> None:
    """Walk +10 east on the flat stone arena within 30 s."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot1")
    await _spawn_on_arena(bot, "TestBot1")
    try:
        x0, y0, z0 = bot.position
        await bot.walk_to(x0 + 10, y0, z0, timeout=30.0)
        x1, _, z1 = bot.position
        assert x1 - x0 > 8.0, f"only moved {x1 - x0:.2f} east"
        assert abs(z1 - z0) < 2.0, f"unexpected z drift: {z1 - z0:.2f}"
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_walk_to_diagonal_then_return(live_server) -> None:
    """Diagonal 15+15 NE, then walk back to origin."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot2")
    await _spawn_on_arena(bot, "TestBot2")
    try:
        x0, y0, z0 = bot.position
        await bot.walk_to(x0 + 15, y0, z0 + 15, timeout=45.0)
        assert bot.x > x0 + 12
        assert bot.z > z0 + 12
        await bot.walk_to(x0, y0, z0, timeout=45.0)
        assert abs(bot.x - x0) < 2.0
        assert abs(bot.z - z0) < 2.0
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_off_arena_target_raises_no_path_or_timeout(live_server) -> None:
    """A target 200 blocks beyond the 30-radius arena edge has no floor —
    A* exhausts its node budget and raises NoPathFound (or times out)."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot3")
    await _spawn_on_arena(bot, "TestBot3")
    try:
        with pytest.raises((NoPathFound, WalkTimeout)):
            await bot.walk_to(bot.x + 200, bot.y, bot.z, timeout=8.0)
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)
