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
