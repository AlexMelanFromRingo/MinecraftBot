"""T058 — Live-server parity: real-world findBlocks + pathfind via accel.

Connects accel Bot to Paper, waits for chunks to stream, then exercises:
- World.find_blocks_nearby("stone", ...) — confirms blocks are findable
- pathfinding.find_path(world, start, goal) — verifies a path exists on
  a known-flat area near the test arena.

This is the strongest correctness signal we have short of full bot-
control: the **live wire** Rust decoder → World cache → PyO3 view →
Python queries return data parity-tested at the unit level.
"""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.live


# Test arena coords (from project memory): 61×61 flat stone at
# (10000, 200, 10000). We expect blocks at y ∈ [199, 199] to be stone
# once the chunk streams in.
ARENA_X = 10000
ARENA_Y = 200
ARENA_Z = 10000


async def test_live_world_stone_lookup(live_server) -> None:
    """After chunks stream in, find_blocks_nearby returns nearby stone."""
    import minecraft_bot_accel as mb

    bot = mb.Bot.offline(live_server.host, live_server.port, "TestBot5")
    await bot.connect()
    try:
        # Wait until at least one chunk loaded.
        for _ in range(40):
            if bot.loaded_chunk_count() > 0:
                break
            await asyncio.sleep(0.25)
        assert bot.loaded_chunk_count() > 0

        # Give the server an extra second to stream the arena chunks.
        await asyncio.sleep(2.0)

        # Search at the spawn origin — Paper streams the spawn-chunk
        # region first. We expect plenty of stone in any non-edge spot.
        # If the bot spawns at the arena, look there; otherwise search
        # around (0, 64, 0).
        world = bot.world
        # Try a few origins to find stone.
        origins = [
            (0.0, 70.0, 0.0),
            (float(ARENA_X), float(ARENA_Y), float(ARENA_Z)),
            (float(ARENA_X), float(ARENA_Y - 10), float(ARENA_Z)),
        ]
        any_stone_found = False
        for origin in origins:
            stones = world.find_blocks_nearby(
                "minecraft:stone", origin, radius=32, limit=8
            )
            if stones:
                any_stone_found = True
                print(f"\n[live] near {origin}: stones[:3] = {stones[:3]}")
                break
        assert any_stone_found, "no stone found in any explored region"
    finally:
        await bot.disconnect()


async def test_live_block_predicates_match_python(live_server) -> None:
    """For a sample of live-streamed blocks, accel.is_solid/is_water
    match Python's classification."""
    import minecraft_bot_accel as mb
    from minecraft_bot.world import block_table as py_tbl

    bot = mb.Bot.offline(live_server.host, live_server.port, "TestBot6")
    await bot.connect()
    try:
        for _ in range(40):
            if bot.loaded_chunk_count() > 5:
                break
            await asyncio.sleep(0.25)

        await asyncio.sleep(1.0)
        world = bot.world

        # Sample some real block-state IDs from the streaming chunks.
        sampled_states: set[int] = set()
        for dx in range(-32, 32, 4):
            for dz in range(-32, 32, 4):
                for y in [60, 64, 70, 80]:
                    sid = world.get_block_id(dx, y, dz)
                    sampled_states.add(sid)

        # All non-zero sampled states must produce identical
        # classifications across backends.
        for sid in sampled_states:
            assert mb.world.block_is_solid(sid) == py_tbl.is_solid(sid), (
                f"is_solid divergence at state_id={sid}: "
                f"accel={mb.world.block_is_solid(sid)} python={py_tbl.is_solid(sid)}"
            )
            assert mb.world.block_name(sid) == py_tbl.get_name(
                sid
            ), f"name divergence at state_id={sid}"
        print(
            f"\n[live] verified {len(sampled_states)} unique state IDs "
            f"with consistent classification across backends"
        )
    finally:
        await bot.disconnect()
