#!/usr/bin/env python3
"""US5 quickstart — follow a summoned villager."""

from __future__ import annotations

import asyncio
import os

from minecraft_bot.bot import Bot

HOST = os.environ.get("MINECRAFT_BOT_TEST_HOST", "172.26.160.1")
PORT = int(os.environ.get("MINECRAFT_BOT_TEST_PORT", "25565"))


async def main() -> None:
    async with Bot.offline(HOST, PORT, "TestBot5") as bot:
        await bot.command(f"tp TestBot5 10000 200 10000")
        await asyncio.sleep(3.0)
        await bot.command(
            f"summon minecraft:villager 10008 200 10000 {{NoAI:1b}}"
        )
        await asyncio.sleep(3.0)
        villagers = [e for e in bot.entities.all() if type(e).__name__ == "Villager"]
        if not villagers:
            print("no villager spawned")
            return
        target = villagers[0]
        print(f"following villager eid={target.eid}")
        try:
            await bot.follow(target.eid, distance=2.0, timeout=15.0)
        except Exception as exc:
            print(f"follow ended: {type(exc).__name__}")
        print(f"final distance: {bot.distance_to(target.eid):.1f}")
        await bot.command("kill @e[type=minecraft:villager,distance=..20]")


if __name__ == "__main__":
    asyncio.run(main())
