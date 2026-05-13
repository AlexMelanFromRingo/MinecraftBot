"""SC-008 smoke wall-clock guard (T133).

Runs the US1 (connect) + US2 (decode) + US3 (send) acceptance smoke
sequence inline and asserts total wall-clock time stays under 120 s.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from minecraft_bot.connection import Connection
from minecraft_bot.protocol.v763.packets.play.serverbound import (
    arm_animation as sb_arm,
)
from minecraft_bot.protocol.v763.states import ConnectionState

pytestmark = pytest.mark.live


async def test_sc008_smoke_under_120_seconds(live_server) -> None:
    t0 = time.monotonic()

    # US1: connect.
    conn = Connection.offline(live_server.host, live_server.port, "TestBot3")
    await conn.connect()
    assert conn.state == ConnectionState.PLAY
    assert conn.entity_id is not None

    # US2: keep the connection alive for a moment so a few clientbound
    # packets land + decode without UnknownPacketId errors.
    await asyncio.sleep(2.0)

    # US3: send a benign serverbound packet — arm_animation, no side-effects.
    await conn.send(sb_arm.ArmAnimation(hand=0))

    await conn.disconnect()
    elapsed = time.monotonic() - t0
    assert elapsed < 120.0, f"smoke took {elapsed:.1f}s; target < 120s"
    print(f"\n  US1+US2+US3 smoke: {elapsed:.1f}s")
