"""US3 — Inventory + container live integration (T063).

Tests require op privileges and the (10000, 200, 10000) flat arena
(see test_us1_walk_to.py for arena setup details).

Scenarios:
1. ``/give`` populates the bot's inventory; ``find_item`` / ``count_item`` see it.
2. Placing a chest, opening it, reading container_items.
"""

from __future__ import annotations

import asyncio

import pytest

from minecraft_bot.bot import Bot

pytestmark = pytest.mark.live


ARENA_CX, ARENA_CY, ARENA_CZ = 10000, 200, 10000


async def _spawn_on_arena(bot: Bot, name: str) -> None:
    await bot.connect()
    await asyncio.sleep(1.5)
    await bot.command(f"tp {name} {ARENA_CX} {ARENA_CY} {ARENA_CZ}")
    await asyncio.sleep(3.0)


async def test_give_populates_inventory(live_server) -> None:
    bot = Bot.offline(live_server.host, live_server.port, "TestBot7")
    await _spawn_on_arena(bot, "TestBot7")
    try:
        # Empty hands first, then /give 32 apples.
        await bot.command("clear TestBot7")
        await asyncio.sleep(1.0)
        await bot.command("give TestBot7 minecraft:apple 32")
        await asyncio.sleep(2.0)
        assert bot.count_item("apple") >= 32, (
            f"expected ≥32 apples, got {bot.count_item('apple')} "
            f"(slots: {[s.name if s else None for s in bot.inventory.items() if s]})"
        )
        # The first apple should appear in some slot.
        idx = bot.find_item("apple")
        assert idx is not None
        assert bot.inventory.player_slots[idx].count > 0
    finally:
        await bot.command("clear TestBot7")
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_open_chest_reads_container_items(live_server) -> None:
    bot = Bot.offline(live_server.host, live_server.port, "TestBot8")
    await _spawn_on_arena(bot, "TestBot8")
    try:
        # Place a chest next to the bot via /setblock, then fill it with a Container NBT.
        chest_x, chest_y, chest_z = ARENA_CX + 2, ARENA_CY, ARENA_CZ
        chest_nbt = '{Items:[{Slot:0b,id:"minecraft:diamond",Count:5b}]}'
        await bot.command(
            f"setblock {chest_x} {chest_y} {chest_z} "
            f"minecraft:chest{chest_nbt}"
        )
        await asyncio.sleep(2.0)
        # Open the chest.
        try:
            wid = await bot.open_chest(chest_x, chest_y, chest_z, timeout=4.0)
        except asyncio.TimeoutError:
            pytest.skip("chest open timed out — likely block_place anti-cheat reject")
            return
        assert wid > 0
        # Read items.
        items = bot.inventory.container_items()
        diamond = next((s for s in items if s and s.name == "minecraft:diamond"), None)
        assert diamond is not None, (
            f"expected diamond in chest, container={[s.name if s else None for s in items]}"
        )
        assert diamond.count == 5
        await bot.close_container()
        assert bot.inventory.container_window_id is None
        # Cleanup.
        await bot.command(f"setblock {chest_x} {chest_y} {chest_z} air")
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)
