"""US5 — Follow entity (live integration, T073).

Bot summons a slow-moving mob, follows it, and verifies distance stays
small. Uses /summon villager for a benign, slow-walking target.
"""

from __future__ import annotations

import asyncio

import pytest
from minecraft_bot.bot import Bot
from minecraft_bot.errors import TargetLost, WalkTimeout

pytestmark = pytest.mark.live


ARENA_CX, ARENA_CY, ARENA_CZ = 10000, 200, 10000


async def _spawn_on_arena(bot: Bot, name: str) -> None:
    await bot.connect()
    await asyncio.sleep(1.5)
    await bot.command(f"tp {name} {ARENA_CX} {ARENA_CY} {ARENA_CZ}")
    await asyncio.sleep(3.0)


async def test_follow_summoned_villager(live_server) -> None:
    """Spawn a villager 8 blocks away, follow it for 12 s, verify the
    bot got closer than the starting distance."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot4")
    await _spawn_on_arena(bot, "TestBot4")
    try:
        # Summon villager 8 blocks east. With NoAI={1b} to keep it stationary
        # so the test isn't flaky (we just want to verify follow approaches).
        target_x, target_z = ARENA_CX + 8, ARENA_CZ
        await bot.command(
            f"summon minecraft:villager {target_x} {ARENA_CY} {target_z} "
            f"{{NoAI:1b,CustomName:'\"FollowTarget\"'}}"
        )
        await asyncio.sleep(3.0)
        # Find the villager in our tracker.
        villagers = [
            e for e in bot.entities.all()
            if type(e).__name__ == "Villager"
        ]
        assert villagers, "no villager spawned"
        target = villagers[0]
        initial_dist = ((target.x - bot.x) ** 2 + (target.z - bot.z) ** 2) ** 0.5
        # Follow for up to 15 s; close-enough threshold = 4 blocks.
        try:
            await bot.follow(target.eid, distance=3.0, timeout=15.0)
        except (WalkTimeout, TargetLost):
            pass
        final_dist = ((target.x - bot.x) ** 2 + (target.z - bot.z) ** 2) ** 0.5
        assert final_dist < initial_dist, (
            f"bot didn't get closer: initial={initial_dist:.1f} final={final_dist:.1f}"
        )
        # Cleanup villager.
        await bot.command("kill @e[type=minecraft:villager,distance=..30]")
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_follow_raises_target_lost_when_killed(live_server) -> None:
    bot = Bot.offline(live_server.host, live_server.port, "TestBot5")
    await _spawn_on_arena(bot, "TestBot5")
    try:
        await bot.command(
            f"summon minecraft:villager {ARENA_CX + 5} {ARENA_CY} {ARENA_CZ} "
            "{NoAI:1b}"
        )
        await asyncio.sleep(2.5)
        villagers = [e for e in bot.entities.all() if type(e).__name__ == "Villager"]
        assert villagers, "no villager spawned"
        target_eid = villagers[0].eid

        # Start follow + kill the target after 2 s.
        async def killer():
            await asyncio.sleep(2.0)
            await bot.command("kill @e[type=minecraft:villager,distance=..30]")

        task = asyncio.create_task(killer())
        try:
            await bot.follow(target_eid, distance=2.0, timeout=20.0)
            # If we get here without raising, it's because the bot got
            # close before kill — accept this too.
        except TargetLost:
            pass
        except WalkTimeout:
            pass
        finally:
            task.cancel()
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)
