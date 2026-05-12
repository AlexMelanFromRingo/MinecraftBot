#!/usr/bin/env python3
"""US1 quickstart — connect + walk_to a target on the arena.

Usage::

    PYTHONPATH=python python tools/quickstart_us1.py
"""

from __future__ import annotations

import asyncio
import os

from minecraft_bot.bot import Bot

HOST = os.environ.get("MINECRAFT_BOT_TEST_HOST", "172.26.160.1")
PORT = int(os.environ.get("MINECRAFT_BOT_TEST_PORT", "25565"))


async def main() -> None:
    async with Bot.offline(HOST, PORT, "TestBot1") as bot:
        await bot.command(f"tp TestBot1 10000 200 10000")
        await asyncio.sleep(3.0)
        print(f"spawned at ({bot.x:.1f}, {bot.y:.1f}, {bot.z:.1f})")
        target_x = bot.x + 10
        await bot.walk_to(target_x, bot.y, bot.z, timeout=30.0)
        print(f"arrived at ({bot.x:.1f}, {bot.y:.1f}, {bot.z:.1f})")


if __name__ == "__main__":
    asyncio.run(main())
