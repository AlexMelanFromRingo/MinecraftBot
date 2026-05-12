#!/usr/bin/env python3
"""US7 quickstart — chat in + out."""

from __future__ import annotations

import asyncio
import os
import time

from minecraft_bot.bot import Bot
from minecraft_bot.events import ChatMessageEvent

HOST = os.environ.get("MINECRAFT_BOT_TEST_HOST", "172.26.160.1")
PORT = int(os.environ.get("MINECRAFT_BOT_TEST_PORT", "25565"))


async def main() -> None:
    async with Bot.offline(HOST, PORT, "TestBot1") as bot:
        seen: list[str] = []

        @bot.on(ChatMessageEvent)
        def on_chat(e: ChatMessageEvent) -> None:
            seen.append(e.raw)

        nonce = f"hello-{int(time.time())}"
        await bot.say(nonce)
        await asyncio.sleep(2.0)
        print(f"sent: {nonce}; received {len(seen)} chat events")


if __name__ == "__main__":
    asyncio.run(main())
