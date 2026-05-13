"""SC-003 long-uptime live test (T131).

The spec requires verifying the bot can survive an extended idle
session without disconnect. Full target is 10 minutes; this file
runs that duration when the ``slow`` marker is selected.

Use the existing 60-second smoke ``test_long_uptime.py`` for the
short variant.

Env::

    SC003_UPTIME_SECONDS  (override; default 660 = 11 min)
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest
from minecraft_bot.bot import Bot

pytestmark = [pytest.mark.live, pytest.mark.slow]


UPTIME_SECONDS = int(os.environ.get("SC003_UPTIME_SECONDS", "660"))


async def test_sc003_eleven_minute_uptime(live_server) -> None:
    bot = Bot.offline(live_server.host, live_server.port, "TestBot1")
    await bot.connect()
    try:
        await bot.command("tp TestBot1 10000 200 10000")
        await asyncio.sleep(3.0)
        start = time.monotonic()
        while time.monotonic() - start < UPTIME_SECONDS:
            await asyncio.sleep(5.0)
            elapsed = time.monotonic() - start
            assert bot.is_connected, (
                f"bot disconnected at t+{elapsed:.0f}s of {UPTIME_SECONDS}s"
            )
        assert bot.is_connected
        assert bot.health > 0
    finally:
        await bot.disconnect()
