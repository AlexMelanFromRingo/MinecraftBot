#!/usr/bin/env python3
"""US4 quickstart — survive: dig + effect + auto_eat."""

from __future__ import annotations

import asyncio
import os

from minecraft_bot.bot import Bot

HOST = os.environ.get("MINECRAFT_BOT_TEST_HOST", "172.26.160.1")
PORT = int(os.environ.get("MINECRAFT_BOT_TEST_PORT", "25565"))


async def main() -> None:
    async with Bot.offline(HOST, PORT, "TestBot4") as bot:
        await bot.command(f"tp TestBot4 10000 200 10000")
        await asyncio.sleep(3.0)
        # Place dirt and dig.
        await bot.command("setblock 10002 200 10000 dirt")
        await asyncio.sleep(1.0)
        await bot.dig(10002, 200, 10000)
        print("dirt broken; air now:", bot.world.get_block_name(10002, 200, 10000))
        # Apply speed effect and read it.
        await bot.command("effect give TestBot4 minecraft:speed 30 1")
        await asyncio.sleep(2.0)
        print("active effects:", bot.effects.names())
        await bot.command("effect clear TestBot4")


if __name__ == "__main__":
    asyncio.run(main())
