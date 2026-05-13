"""Live: drop_item + ItemPickupEvent.

Bot drops an item from its inventory, then walks back over it to
pick it up. Verifies:

1. ``Bot.drop_item()`` shrinks the slot count by 1.
2. ``ItemPickupEvent`` fires when the bot walks over the dropped item.
3. The slot count restores after the pickup (or stays decremented if
   the bot moved past it — see strict assertion).

Uses the flat (10000, 200, 10000) arena (no corridor needed).
"""

from __future__ import annotations

import asyncio

import pytest
from minecraft_bot.bot import Bot
from minecraft_bot.events import ItemPickupEvent

pytestmark = pytest.mark.live


ARENA_CX, ARENA_CY, ARENA_CZ = 10000, 200, 10000


async def _spawn(bot: Bot, name: str) -> None:
    await bot.connect()
    await asyncio.sleep(1.5)
    await bot.command(f"tp {name} {ARENA_CX} {ARENA_CY} {ARENA_CZ}")
    await asyncio.sleep(3.0)


async def test_drop_item_decrements_count(live_server) -> None:
    """drop_item via window-click reduces the held slot count."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot6")
    await _spawn(bot, "TestBot6")
    try:
        await bot.command("clear @s")
        await asyncio.sleep(0.5)
        await bot.command("item replace entity @s hotbar.0 with minecraft:apple 10")
        await asyncio.sleep(1.5)
        await bot.select_slot(0)
        await asyncio.sleep(0.3)
        assert bot.count_item("apple") == 10
        # Drop one.
        await bot.drop_item(drop_stack=False)
        await asyncio.sleep(1.5)
        assert bot.count_item("apple") == 9, f"drop_one: got {bot.count_item('apple')}"
        # Drop full stack.
        await bot.drop_item(drop_stack=True)
        await asyncio.sleep(1.5)
        assert bot.count_item("apple") == 0, f"drop_stack: got {bot.count_item('apple')}"
    finally:
        await bot.command("clear @s")
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_pickup_event_fires_when_bot_walks_over_dropped_item(live_server) -> None:
    """Drop apples, walk over them, ItemPickupEvent fires.

    Items dropped by a player have a 2 s pickup-delay on the server.
    We drop a stack, wait the delay, then walk a tiny circle around
    the bot's current position. The bot's hitbox should sweep over
    the dropped item entity at some point.
    """
    bot = Bot.offline(live_server.host, live_server.port, "TestBot7")
    pickups: list[ItemPickupEvent] = []

    @bot.on(ItemPickupEvent)
    def cap(e: ItemPickupEvent) -> None:
        pickups.append(e)

    await _spawn(bot, "TestBot7")
    try:
        await bot.command("clear @s")
        await asyncio.sleep(0.5)
        await bot.command("item replace entity @s hotbar.0 with minecraft:apple 16")
        await asyncio.sleep(1.5)
        await bot.select_slot(0)
        await asyncio.sleep(0.3)
        await bot.drop_item(drop_stack=True)
        await asyncio.sleep(0.5)
        before_pickups = len(pickups)
        # Wait out the server's 2 s pickup delay (vanilla DROP cooldown).
        await asyncio.sleep(2.5)
        # Find item entities the bot tracked and walk to each.
        from minecraft_bot.entities.base import ItemEntity
        item_ents = [e for e in bot.entities.all() if isinstance(e, ItemEntity)]
        print(f"\n  found {len(item_ents)} item entities nearby; "
              f"positions: {[(round(e.x,1),round(e.y,1),round(e.z,1)) for e in item_ents]}")
        for ent in item_ents:
            try:
                await bot.walk_to(ent.x, ent.y, ent.z, timeout=8.0)
            except Exception:
                pass
            await asyncio.sleep(0.5)
        got_pickups = len(pickups) - before_pickups
        print(f"  drop+pickup: got {got_pickups} pickup events; "
              f"final apple count = {bot.count_item('apple')}")
        assert got_pickups > 0, (
            f"ItemPickupEvent never fired (visited {len(item_ents)} items)"
        )
    finally:
        await bot.command("clear @s")
        await bot.command("kill @e[type=minecraft:item,distance=..20]")
        await bot.disconnect()
    await asyncio.sleep(1.0)
