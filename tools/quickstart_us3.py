#!/usr/bin/env python3
"""US3 quickstart — inventory + open chest."""

from __future__ import annotations

import asyncio
import os

from minecraft_bot.bot import Bot

HOST = os.environ.get("MINECRAFT_BOT_TEST_HOST", "172.26.160.1")
PORT = int(os.environ.get("MINECRAFT_BOT_TEST_PORT", "25565"))


async def main() -> None:
    async with Bot.offline(HOST, PORT, "TestBot3") as bot:
        await bot.command(f"tp TestBot3 10000 200 10000")
        await asyncio.sleep(3.0)
        await bot.command("clear TestBot3")
        await bot.command("give TestBot3 minecraft:diamond_sword 1")
        await asyncio.sleep(1.5)
        idx = bot.find_item("diamond_sword")
        slot = bot.inventory.player_slots[idx] if idx is not None else None
        if slot:
            print(f"diamond_sword in slot {idx}; enchants={slot.enchantments}")
        # Place a chest and open it.
        await bot.command("setblock 10002 200 10000 chest")
        await asyncio.sleep(0.5)
        await bot.command(
            'data merge block 10002 200 10000 '
            '{Items:[{Slot:0b,id:"minecraft:gold_ingot",Count:16b}]}'
        )
        await asyncio.sleep(1.0)
        await bot.open_chest(10002, 200, 10000, timeout=5.0)
        for i, s in enumerate(bot.inventory.container_items()):
            if s:
                print(f"  chest slot {i}: {s.name} x {s.count}")
        await bot.close_container()
        await bot.command("setblock 10002 200 10000 air")
        await bot.command("clear TestBot3")


if __name__ == "__main__":
    asyncio.run(main())
