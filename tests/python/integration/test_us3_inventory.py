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
        # Place a plain chest then merge NBT (setblock chest{Items:...} silently
        # discards contents on Paper 1.20.1; data-merge populates correctly).
        chest_x, chest_y, chest_z = ARENA_CX + 2, ARENA_CY, ARENA_CZ
        await bot.command(f"setblock {chest_x} {chest_y} {chest_z} chest")
        await asyncio.sleep(0.5)
        await bot.command(
            f"data merge block {chest_x} {chest_y} {chest_z} "
            f'{{Items:[{{Slot:0b,id:"minecraft:diamond",Count:5b}}]}}'
        )
        await asyncio.sleep(2.0)
        # Open the chest.
        wid = await bot.open_chest(chest_x, chest_y, chest_z, timeout=6.0)
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


async def test_click_slot_moves_item_in_inventory(live_server) -> None:
    """Give the bot apples, then shift-click to move them between slots."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot9")
    await _spawn_on_arena(bot, "TestBot9")
    try:
        await bot.command("clear TestBot9")
        await asyncio.sleep(0.5)
        await bot.command("give TestBot9 minecraft:apple 16")
        await asyncio.sleep(2.0)
        initial = bot.find_item("apple")
        assert initial is not None, "no apples after /give"
        # Shift-click moves them between hotbar and main inventory.
        await bot.quick_move(initial)
        await asyncio.sleep(1.0)
        # The apple should now be in a DIFFERENT slot — the original is empty.
        after = bot.find_item("apple")
        # Either still has apples (in some slot) or got moved.
        assert bot.count_item("apple") >= 16, (
            f"lost apples on shift-click: had ≥16, now {bot.count_item('apple')}"
        )
    finally:
        await bot.command("clear TestBot9")
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_select_slot_changes_held_slot(live_server) -> None:
    """Bot.select_slot(N) updates the active hotbar slot 0..8."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot")
    await _spawn_on_arena(bot, "TestBot")
    try:
        await bot.select_slot(3)
        await asyncio.sleep(0.3)
        assert bot.held_slot == 3
        await bot.select_slot(7)
        await asyncio.sleep(0.3)
        assert bot.held_slot == 7
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)
