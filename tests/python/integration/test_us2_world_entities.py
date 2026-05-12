"""US2 — World cache + Entity tracker (live integration).

Acceptance scenarios from spec.md US2:

1. After connect + chunk-load wait, ``find_blocks_nearby`` returns
   blocks the server has streamed (we use stone on the test arena).
2. ``nearby_entities`` finds the bot after a `/summon` and the entity
   subclass is typed (e.g., a summoned Sheep has ``wool_color``).
3. ``Bot.attack`` against a summoned entity reduces the world entity
   count or marks the entity destroyed (sheep have 8 HP; one hit at
   gamemode adventure won't kill it but tests packet plumbing).

Requires the live server fixture. Tests teleport to the
(10000, 200, 10000) flat stone arena. Op rights required to /summon.
"""

from __future__ import annotations

import asyncio

import pytest

from minecraft_bot.bot import Bot
from minecraft_bot.entities.types import LOOKUP

pytestmark = pytest.mark.live


ARENA_CX, ARENA_CY, ARENA_CZ = 10000, 200, 10000


async def _spawn_on_arena(bot: Bot, name: str) -> None:
    await bot.connect()
    await asyncio.sleep(1.5)
    await bot.command(f"tp {name} {ARENA_CX} {ARENA_CY} {ARENA_CZ}")
    await asyncio.sleep(3.0)


async def test_find_blocks_nearby_returns_arena_stone(live_server) -> None:
    """The arena floor is 61x61 stone at y=199; the bot stands on top."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot4")
    await _spawn_on_arena(bot, "TestBot4")
    try:
        # Bot.find_blocks_nearby uses bot.position as origin.
        stones = bot.find_blocks_nearby("stone", radius=16, limit=20)
        assert len(stones) >= 5, f"expected several stone hits, got {stones!r}"
        # Closest should be roughly under the bot (y=199, dist ~1.0).
        cx, cy, cz = stones[0]
        assert cy == ARENA_CY - 1, f"closest stone Y should be {ARENA_CY - 1}, got {cy}"
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_nearby_entities_picks_up_summoned_sheep(live_server) -> None:
    bot = Bot.offline(live_server.host, live_server.port, "TestBot5")
    await _spawn_on_arena(bot, "TestBot5")
    try:
        # Summon a red sheep 3 blocks east of the bot.
        await bot.command(
            f"summon minecraft:sheep "
            f"{ARENA_CX + 3} {ARENA_CY} {ARENA_CZ} "
            f'{{Color:14b}}'  # red wool
        )
        await asyncio.sleep(2.5)
        # The tracker should have it now.
        nearby = bot.nearby_entities(radius=10.0)
        sheep_cls = LOOKUP[82]
        sheep = [e for e in nearby if isinstance(e, sheep_cls)]
        assert len(sheep) >= 1, (
            f"expected a Sheep within 10 blocks, got {[type(e).__name__ for e in nearby]}"
        )
        # And the Bot's nearby_entities with type_filter should match.
        sheep_filtered = bot.nearby_entities(radius=10.0, type_filter=sheep_cls)
        assert len(sheep_filtered) == len(sheep)
        # Clean up — kill the sheep so subsequent test runs don't pile up.
        await bot.command(f"kill @e[type=minecraft:sheep,distance=..15]")
        await asyncio.sleep(1.0)
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_attack_packet_routes_to_summoned_target(live_server) -> None:
    """Smoke: send an attack at a summoned entity and verify no disconnect."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot6")
    await _spawn_on_arena(bot, "TestBot6")
    try:
        await bot.command(
            f"summon minecraft:sheep {ARENA_CX + 2} {ARENA_CY} {ARENA_CZ}"
        )
        await asyncio.sleep(4.0)
        nearby = bot.nearby_entities(radius=15.0)
        sheep = [e for e in nearby if type(e).__name__ == "Sheep"]
        assert sheep, f"no sheep spawned (saw {[type(e).__name__ for e in nearby]})"
        target = sheep[0]
        await bot.attack(target.eid)
        await asyncio.sleep(0.5)
        # Bot should still be connected after the attack packet.
        assert bot.is_connected
        await bot.command(f"kill @e[type=minecraft:sheep,distance=..15]")
        await asyncio.sleep(1.0)
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)
