#!/usr/bin/env python3
"""US2 quickstart — observe blocks + entities."""

from __future__ import annotations

import asyncio
import os

from minecraft_bot.bot import Bot

HOST = os.environ.get("MINECRAFT_BOT_TEST_HOST", "172.26.160.1")
PORT = int(os.environ.get("MINECRAFT_BOT_TEST_PORT", "25565"))


async def main() -> None:
    async with Bot.offline(HOST, PORT, "TestBot2") as bot:
        await bot.command(f"tp TestBot2 10000 200 10000")
        await asyncio.sleep(3.0)
        stones = bot.find_blocks_nearby("stone", radius=10, limit=5)
        print(f"nearby stones: {stones}")
        await bot.command(
            f"summon minecraft:sheep 10003 200 10000 {{Color:14b}}"
        )
        await asyncio.sleep(3.0)
        nearby = bot.nearby_entities(radius=10)
        for e in nearby:
            print(f"  {type(e).__name__} eid={e.eid} pos=({e.x:.1f}, {e.y:.1f}, {e.z:.1f})")
        await bot.command("kill @e[type=minecraft:sheep,distance=..15]")


if __name__ == "__main__":
    asyncio.run(main())
