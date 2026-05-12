"""SC-007 onboarding metric (T132).

Measures wall-clock time from ``Connection.offline(...)`` construction
to the bot reaching the PLAY state. SC-007 target: under 30 s on a
warm test environment.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from minecraft_bot.connection import Connection
from minecraft_bot.protocol.v763.states import ConnectionState

pytestmark = pytest.mark.live


async def test_sc007_connect_under_30_seconds(live_server) -> None:
    t0 = time.monotonic()
    conn = Connection.offline(live_server.host, live_server.port, "TestBot2")
    await conn.connect()
    elapsed = time.monotonic() - t0
    try:
        assert conn.state == ConnectionState.PLAY, (
            f"connection didn't reach PLAY state: {conn.state}"
        )
        assert elapsed < 30.0, f"connect took {elapsed:.2f}s; target < 30s"
        print(f"\n  connect-to-PLAY: {elapsed:.2f}s")
    finally:
        await conn.disconnect()
    await asyncio.sleep(1.0)
