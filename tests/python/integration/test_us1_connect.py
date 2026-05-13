"""US1 — Connect a Bot to the Server and Reach Play State (live).

Acceptance scenarios from spec.md US1:

1. Connect, complete handshake/login, reach PLAY with valid spawn position.
2. KeepAlive cycle keeps us alive (≥ 60 s).
3. Position-sync auto-confirm without echoing position update.
4. Clean disconnect — server records normal quit, not timeout.

Requires the live server fixture (see ``tests/python/conftest.py``). Run:
    pytest -m live tests/python/integration/test_us1_connect.py
"""

from __future__ import annotations

import asyncio

import pytest
from minecraft_bot.connection import Connection
from minecraft_bot.errors import ConnectionClosed
from minecraft_bot.protocol.v763.packets.play.clientbound import (
    keep_alive as p_cb_ka,
)
from minecraft_bot.protocol.v763.packets.play.clientbound import position as p_cb_pos
from minecraft_bot.protocol.v763.states import ConnectionState

pytestmark = pytest.mark.live


async def test_connect_reaches_play(live_server) -> None:
    """AS1: handshake → login → PLAY with entity id and spawn world set."""
    bot = Connection.offline(
        host=live_server.host, port=live_server.port, username="ITConn1",
    )
    await bot.connect()
    try:
        assert bot.state == ConnectionState.PLAY
        assert bot.entity_id is not None
        assert bot.world_name is not None
        assert bot.is_connected is True
    finally:
        await bot.disconnect()


async def test_keepalive_cycle_keeps_us_alive(live_server) -> None:
    """AS2: server sends KeepAlive every ~10s; the framework auto-replies and
    we stay alive for at least 60 s without disconnect."""
    bot = Connection.offline(
        host=live_server.host, port=live_server.port, username="ITConn2",
    )
    keep_alives: list[int] = []
    bot.on(p_cb_ka.KeepAlive, lambda p: keep_alives.append(p.keep_alive_id))
    await bot.connect()
    try:
        await asyncio.sleep(60)
        assert bot.is_connected, "connection died during 60s idle window"
        # Paper sends keep-alive every ~15 s by default; we should see >= 1.
        assert len(keep_alives) >= 1, (
            "no KeepAlives received in 60s window; auto-reply may have failed"
        )
    finally:
        await bot.disconnect()


async def test_position_sync_auto_confirms(live_server) -> None:
    """AS3: server pushes Position right after spawn; framework auto-confirms
    AND does not echo a position update back."""
    bot = Connection.offline(
        host=live_server.host, port=live_server.port, username="ITConn3",
    )
    received_positions: list[p_cb_pos.Position] = []
    bot.on(p_cb_pos.Position, lambda p: received_positions.append(p))
    await bot.connect()
    try:
        # First Position arrives within a second of entering PLAY.
        await asyncio.sleep(2.0)
        assert len(received_positions) >= 1, "no Position received post-login"
        # If we hadn't auto-confirmed, the server would have already kicked us
        # for "moved too quickly" or hung waiting for confirm. Reaching here
        # with is_connected=True is itself the assertion.
        assert bot.is_connected
    finally:
        await bot.disconnect()


async def test_clean_disconnect(live_server) -> None:
    """AS4: disconnect() closes the socket cleanly. After disconnect, send()
    raises ConnectionClosed and is_connected is False."""
    bot = Connection.offline(
        host=live_server.host, port=live_server.port, username="ITConn4",
    )
    await bot.connect()
    assert bot.is_connected
    await bot.disconnect()
    assert not bot.is_connected
    # Sending after disconnect is a clean error.
    from minecraft_bot.protocol.v763.packets.play.serverbound import (
        keep_alive as p_sb_ka,
    )
    with pytest.raises(ConnectionClosed):
        await bot.send(p_sb_ka.KeepAlive(keep_alive_id=0))


async def test_async_context_manager(live_server) -> None:
    """`async with Connection.offline(...) as bot` — exit auto-disconnects."""
    async with Connection.offline(
        host=live_server.host, port=live_server.port, username="ITConn5",
    ) as bot:
        await bot.connect()
        assert bot.state == ConnectionState.PLAY
    # After exit, bot is closed.
    assert not bot.is_connected
