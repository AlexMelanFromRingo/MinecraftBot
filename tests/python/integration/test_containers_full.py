"""Live integration: containers beyond chest — furnace + barrel + smelt.

Confirms the `open_block_container` path works for every container
block we model, and that ``Bot.smelt`` correctly places fuel + input
in a furnace.
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


async def test_open_barrel(live_server) -> None:
    """Barrels are vanilla single-block containers (27-slot, like a chest)."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot1")
    await _spawn_on_arena(bot, "TestBot1")
    try:
        bx, by, bz = ARENA_CX + 2, ARENA_CY, ARENA_CZ
        await bot.command(f"setblock {bx} {by} {bz} barrel")
        await asyncio.sleep(1.0)
        await bot.command(
            f"data merge block {bx} {by} {bz} "
            '{Items:[{Slot:0b,id:"minecraft:emerald",Count:7b}]}'
        )
        await asyncio.sleep(1.5)
        wid = await bot.open_block_container(bx, by, bz, timeout=6.0)
        assert wid > 0
        items = bot.inventory.container_items()
        emerald = next((s for s in items if s and s.name == "minecraft:emerald"), None)
        assert emerald is not None and emerald.count == 7
        await bot.close_container()
        await bot.command(f"setblock {bx} {by} {bz} air")
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_open_furnace(live_server) -> None:
    bot = Bot.offline(live_server.host, live_server.port, "TestBot2")
    await _spawn_on_arena(bot, "TestBot2")
    try:
        bx, by, bz = ARENA_CX + 2, ARENA_CY, ARENA_CZ
        await bot.command(f"setblock {bx} {by} {bz} furnace")
        await asyncio.sleep(1.0)
        wid = await bot.open_furnace(bx, by, bz, timeout=6.0)
        assert wid > 0
        # Furnace has 3 slots (input/fuel/output) + 36 inventory; verify.
        assert len(bot.inventory.container_slots) >= 3
        await bot.close_container()
        await bot.command(f"setblock {bx} {by} {bz} air")
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_smelt_places_fuel_and_input(live_server) -> None:
    """Bot.smelt puts raw_iron + coal into a furnace; we verify the
    furnace's container_slots[0] and [1] receive them by re-opening."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot3")
    await _spawn_on_arena(bot, "TestBot3")
    try:
        await bot.command("clear TestBot3")
        await asyncio.sleep(0.5)
        await bot.command("give TestBot3 minecraft:raw_iron 4")
        await asyncio.sleep(0.3)
        await bot.command("give TestBot3 minecraft:coal 4")
        await asyncio.sleep(1.5)
        bx, by, bz = ARENA_CX + 2, ARENA_CY, ARENA_CZ
        await bot.command(f"setblock {bx} {by} {bz} furnace")
        await asyncio.sleep(1.0)
        # Smelt places input + fuel and closes the window.
        await bot.smelt("raw_iron", "coal", bx, by, bz, timeout=8.0)
        # Re-open to verify slots got populated.
        await bot.open_furnace(bx, by, bz, timeout=6.0)
        slots = bot.inventory.container_slots
        # Slot 0 = input, 1 = fuel
        assert slots[0] is not None and slots[0].name == "minecraft:raw_iron"
        assert slots[1] is not None and slots[1].name == "minecraft:coal"
        await bot.close_container()
        await bot.command(f"setblock {bx} {by} {bz} air")
    finally:
        await bot.command("clear TestBot3")
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_open_dispenser(live_server) -> None:
    """Dispensers are 9-slot containers."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot4")
    await _spawn_on_arena(bot, "TestBot4")
    try:
        bx, by, bz = ARENA_CX + 2, ARENA_CY, ARENA_CZ
        await bot.command(f"setblock {bx} {by} {bz} dispenser")
        await asyncio.sleep(1.0)
        wid = await bot.open_block_container(bx, by, bz, timeout=6.0)
        assert wid > 0
        assert len(bot.inventory.container_slots) >= 9
        await bot.close_container()
        await bot.command(f"setblock {bx} {by} {bz} air")
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)
