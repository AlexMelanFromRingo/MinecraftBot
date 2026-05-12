"""T058 (partial) — live Bot connect under the accel backend.

Connects `minecraft_bot_accel.Bot` to the Paper test server,
idles a few seconds, and verifies the World cache filled up
via the packet dispatcher.
"""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.live


async def test_accel_bot_connects_and_loads_chunks(live_server) -> None:
    """Substitution-style smoke: spin up an accel Bot, wait for chunks."""
    import minecraft_bot_accel as mb

    bot = mb.Bot.offline(live_server.host, live_server.port, "TestBot3")
    await bot.connect()
    try:
        eid = await bot.entity_id()
        assert eid is not None, "entity_id should be set after login"

        # Wait up to 5 s for chunks to stream in.
        for _ in range(10):
            await asyncio.sleep(0.5)
            if bot.loaded_chunk_count() > 0:
                break
        loaded = bot.loaded_chunk_count()
        assert loaded > 0, f"expected chunks loaded; got {loaded}"
        print(f"\n[accel-bot-live] {loaded} chunks loaded under PyO3 Bot")

        # World is accessible via the .world property.
        world = bot.world
        assert world.loaded_chunk_count() == loaded
    finally:
        await bot.disconnect()


async def test_accel_bot_position_tracking(live_server) -> None:
    """`synchronize_player_position` packet → Bot.position() reflects
    the server-known position, and World.get_block_name(x, y-1, z) at
    that position returns a sane (typically solid) block name."""
    import minecraft_bot_accel as mb

    bot = mb.Bot.offline(live_server.host, live_server.port, "TestBot9")
    await bot.connect()
    try:
        pos = None
        for _ in range(40):
            pos = await bot.position()
            if pos is not None:
                break
            await asyncio.sleep(0.25)
        assert pos is not None, "position should arrive within 10s"
        x, y, z, yaw, pitch = pos
        print(
            f"\n[live] position: ({x:.2f}, {y:.2f}, {z:.2f}) yaw={yaw:.2f} pitch={pitch:.2f}"
        )

        # Let chunks finish streaming.
        await asyncio.sleep(1.5)

        # Block under the bot's feet — should be solid (we stand on it).
        ix, iy, iz = int(x), int(y), int(z)
        below = bot.world.get_block_name(ix, iy - 1, iz)
        print(f"[live] under feet ({ix},{iy-1},{iz}): {below}")
        # Don't hard-assert the name (depends on server world), but it
        # must be non-air and non-None.
        assert below is not None, "block under feet should be a known block"
        assert below != "minecraft:air", "bot is standing on air?"
    finally:
        await bot.disconnect()
