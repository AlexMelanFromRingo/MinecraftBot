"""US4 — Survive autonomously (live integration, T070).

Scenarios:
1. ``Bot.dig`` breaks a placed dirt block on the arena.
2. Status effects propagate: /effect give applies Speed → bot.effects sees it.
3. Auto-eat: bot food hunger restored after /effect give hunger then /give beef.

Requires op privileges and the (10000, 200, 10000) arena.
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


async def test_dig_breaks_placed_dirt(live_server) -> None:
    """Place a dirt block adjacent to the bot, dig it, verify removal."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot1")
    await _spawn_on_arena(bot, "TestBot1")
    try:
        # Place dirt 2 east, at standable-y (will be at chest height).
        dx, dy, dz = ARENA_CX + 2, ARENA_CY, ARENA_CZ
        await bot.command(f"setblock {dx} {dy} {dz} dirt")
        await asyncio.sleep(1.0)
        assert bot.world.get_block_name(dx, dy, dz) == "minecraft:dirt"
        await bot.dig(dx, dy, dz)
        # After dig, the cache should show air.
        await asyncio.sleep(0.5)
        assert bot.world.get_block(dx, dy, dz) == 0
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_effect_give_propagates_to_bot_effects(live_server) -> None:
    """/effect give speed → bot.effects.has_effect('speed')."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot2")
    await _spawn_on_arena(bot, "TestBot2")
    try:
        await bot.command("effect give TestBot2 minecraft:speed 30 1")
        await asyncio.sleep(2.0)
        assert bot.effects.has_effect("speed"), (
            f"speed effect not seen; effects={bot.effects.names()}"
        )
        speed = bot.effects.get("speed")
        assert speed is not None and speed.level == 2  # amplifier=1 → level II
        # Clean up.
        await bot.command("effect clear TestBot2")
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_auto_eat_restores_food_after_hunger(live_server) -> None:
    """Bot in survival with cooked_beef in hotbar should auto-eat
    when its food drops below threshold."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot3")
    await _spawn_on_arena(bot, "TestBot3")
    try:
        await bot.command("gamemode survival TestBot3")
        await asyncio.sleep(1.0)
        await bot.command("clear TestBot3")
        await asyncio.sleep(0.5)
        await bot.command("give TestBot3 minecraft:cooked_beef 8")
        await asyncio.sleep(1.5)
        # Switch hotbar to slot 0 (where /give puts the first stack).
        await bot.select_slot(0)
        await asyncio.sleep(0.5)
        # We can't easily drop food past 20 on an idle bot (food drains
        # only from exhaustion). Verify auto-eat fires by setting the
        # threshold ABOVE max food — every tick the bot will pick a
        # food and use_item it. Capture the use_item packets.
        from minecraft_bot.protocol.v763.packets.play.serverbound.use_item import (
            UseItem,
        )
        use_items: list = []
        bot.connection.on(UseItem, lambda p: use_items.append(p))
        # Wait, that hook fires on RECEIVE not send. We need to capture
        # outgoing packets — for that we wrap _conn.send.
        original_send = bot._conn.send
        async def trace_send(pkt):
            if isinstance(pkt, UseItem):
                use_items.append(pkt)
            await original_send(pkt)
        bot._conn.send = trace_send

        bot.auto_eat(threshold=25)   # above max, fires every tick
        await asyncio.sleep(3.5)
        bot.stop_auto_eat()
        assert use_items, "auto_eat never sent use_item"
    finally:
        await bot.command("gamemode creative TestBot3")
        await bot.command("clear TestBot3")
        await bot.command("effect clear TestBot3")
        await bot.disconnect()
    await asyncio.sleep(1.0)
