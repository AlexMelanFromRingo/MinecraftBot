"""SC-006 condensed: bot stays connected for 60 s idle (T092, slow).

The full 10-minute test is too slow for CI; this is a smoke version
that catches the most common stay-alive bugs (keep-alive miss, anti-
cheat false-positives, physics drift). The full 10-min version can be
enabled by editing UPTIME_SECONDS below.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from minecraft_bot.bot import Bot

pytestmark = [pytest.mark.live, pytest.mark.slow]


UPTIME_SECONDS = 60   # bump to 600 for full SC-006


async def test_bot_stays_connected_idle(live_server) -> None:
    """Bot connects, idles for UPTIME_SECONDS, stays connected throughout."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot4")
    await bot.connect()
    try:
        await bot.command("tp TestBot4 10000 200 10000")
        await asyncio.sleep(3.0)
        start = time.monotonic()
        while time.monotonic() - start < UPTIME_SECONDS:
            await asyncio.sleep(2.0)
            assert bot.is_connected, (
                f"bot disconnected at t+{time.monotonic() - start:.0f}s "
                f"(of {UPTIME_SECONDS}s)"
            )
        # Final check.
        assert bot.is_connected
        assert bot.health > 0
        # Position should be on the arena (or near it).
        assert abs(bot.x - 10000) < 5
        assert abs(bot.z - 10000) < 5
    finally:
        await bot.disconnect()
