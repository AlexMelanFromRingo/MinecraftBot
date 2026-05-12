#!/usr/bin/env python3
"""US6 quickstart — behaviour tree."""

from __future__ import annotations

import asyncio
import os

from minecraft_bot.behaviour import (
    BehaviourRunner, EatWhenHungry, Selector, WalkTo,
)
from minecraft_bot.bot import Bot

HOST = os.environ.get("MINECRAFT_BOT_TEST_HOST", "172.26.160.1")
PORT = int(os.environ.get("MINECRAFT_BOT_TEST_PORT", "25565"))


async def main() -> None:
    async with Bot.offline(HOST, PORT, "WalkBot1") as bot:
        await bot.command(f"tp WalkBot1 10000 200 10000")
        await asyncio.sleep(3.0)
        tree = Selector([
            EatWhenHungry(threshold=15),
            WalkTo(10010, 200, 10000, timeout=30.0),
        ])
        runner = BehaviourRunner(tick_dt=0.5)
        result = await runner.run(tree, bot, max_ticks=40)
        print(f"tree result: {result}")
        print(f"final pos: ({bot.x:.1f}, {bot.y:.1f}, {bot.z:.1f})")


if __name__ == "__main__":
    asyncio.run(main())
