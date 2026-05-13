"""Offline-only Connection tests (no socket I/O).

Live connect/login/keep-alive tests live in
``tests/python/integration/test_us1_*.py`` (Phase 3 final batch) and
need a running Paper server. These offline tests cover construction,
validation, factory shape, hook plumbing, and the offline_uuid helper.
"""

from __future__ import annotations

import asyncio
import uuid as _uuid

import pytest
from minecraft_bot.connection import (
    Connection,
    Reconnected,
    ReconnectPolicy,
    offline_uuid,
)
from minecraft_bot.errors import ConnectionClosed
from minecraft_bot.protocol import V_1_20_1, ProtocolVersion
from minecraft_bot.protocol.v763.packets.play.clientbound import keep_alive as p_ka

# --- construction ----------------------------------------------------------


def test_offline_factory_basic() -> None:
    c = Connection.offline(host="127.0.0.1", port=25565, username="Bot")
    assert c.host == "127.0.0.1"
    assert c.port == 25565
    assert c.username == "Bot"
    assert c.version == V_1_20_1
    assert c.is_connected is False
    assert c.compression_threshold == -1


def test_offline_factory_rejects_unsupported_protocol() -> None:
    fake = ProtocolVersion(number=999, display_name="future")
    with pytest.raises(ValueError, match="protocol 763"):
        Connection.offline(host="x", port=1, username="b", version=fake)


def test_offline_factory_rejects_empty_username() -> None:
    with pytest.raises(ValueError):
        Connection.offline(host="x", port=1, username="")


def test_offline_factory_rejects_invalid_buffer_size() -> None:
    with pytest.raises(ValueError):
        Connection.offline(host="x", port=1, username="b", write_buffer_size=0)
    with pytest.raises(ValueError):
        Connection.offline(host="x", port=1, username="b", write_buffer_size=-1)


def test_default_reconnect_policy_when_enabled() -> None:
    c = Connection.offline(host="x", port=1, username="b", auto_reconnect=True)
    # Internal — verify default policy was substituted.
    assert c._reconnect_policy.max_attempts == 5  # type: ignore[attr-defined]


# --- offline_uuid ----------------------------------------------------------


def test_offline_uuid_deterministic() -> None:
    a = offline_uuid("Notch")
    b = offline_uuid("Notch")
    assert a == b


def test_offline_uuid_is_version_3() -> None:
    u = offline_uuid("Bot")
    assert u.version == 3


def test_offline_uuid_known_notch_value() -> None:
    """The Notchian offline UUID for username "Notch" is well-known."""
    expected = _uuid.UUID("b50ad385-829d-3141-a216-7e7d7539ba7f")
    assert offline_uuid("Notch") == expected


# --- ReconnectPolicy ------------------------------------------------------


def test_reconnect_policy_defaults() -> None:
    p = ReconnectPolicy()
    assert p.max_attempts == 5
    assert p.initial_delay == 1.0
    assert p.max_delay == 30.0
    assert p.multiplier == 2.0
    assert p.jitter == 0.25


def test_reconnect_policy_validation() -> None:
    with pytest.raises(ValueError):
        ReconnectPolicy(max_attempts=-1)
    with pytest.raises(ValueError):
        ReconnectPolicy(initial_delay=0)
    with pytest.raises(ValueError):
        ReconnectPolicy(initial_delay=10, max_delay=5)
    with pytest.raises(ValueError):
        ReconnectPolicy(multiplier=0.5)
    with pytest.raises(ValueError):
        ReconnectPolicy(jitter=1.0)


# --- send() guard ----------------------------------------------------------


@pytest.mark.asyncio
async def test_send_on_closed_raises() -> None:
    c = Connection.offline(host="127.0.0.1", port=1, username="B")
    with pytest.raises(ConnectionClosed):
        await c.send(p_ka.KeepAlive(keep_alive_id=1))


# --- hooks (without live wire) --------------------------------------------


def test_hook_register_and_off() -> None:
    c = Connection.offline(host="x", port=1, username="b")
    received: list[int] = []

    def handler(pkt):
        received.append(pkt.keep_alive_id)

    sub = c.on(p_ka.KeepAlive, handler)
    assert isinstance(c._handlers[p_ka.KeepAlive], list)  # type: ignore[attr-defined]
    assert handler in c._handlers[p_ka.KeepAlive]  # type: ignore[attr-defined]

    c._dispatch(p_ka.KeepAlive(keep_alive_id=42))  # type: ignore[attr-defined]
    assert received == [42]

    sub.cancel()
    assert handler not in c._handlers[p_ka.KeepAlive]  # type: ignore[attr-defined]

    c._dispatch(p_ka.KeepAlive(keep_alive_id=99))  # type: ignore[attr-defined]
    assert received == [42], "handler still firing after cancel()"


def test_hook_off_idempotent() -> None:
    c = Connection.offline(host="x", port=1, username="b")
    sub = c.on(p_ka.KeepAlive, lambda p: None)
    c.off(sub)
    c.off(sub)  # double cancel must not raise


@pytest.mark.asyncio
async def test_wait_for_resolves_on_match() -> None:
    c = Connection.offline(host="x", port=1, username="b")

    async def producer():
        await asyncio.sleep(0.01)
        c._dispatch(p_ka.KeepAlive(keep_alive_id=7))  # type: ignore[attr-defined]

    asyncio.create_task(producer())
    result = await c.wait_for(p_ka.KeepAlive, timeout=1.0)
    assert result.keep_alive_id == 7


@pytest.mark.asyncio
async def test_wait_for_timeout() -> None:
    c = Connection.offline(host="x", port=1, username="b")
    with pytest.raises(asyncio.TimeoutError):
        await c.wait_for(p_ka.KeepAlive, timeout=0.05)


@pytest.mark.asyncio
async def test_wait_for_predicate() -> None:
    c = Connection.offline(host="x", port=1, username="b")

    async def producer():
        await asyncio.sleep(0.01)
        c._dispatch(p_ka.KeepAlive(keep_alive_id=1))  # type: ignore[attr-defined]
        c._dispatch(p_ka.KeepAlive(keep_alive_id=2))  # type: ignore[attr-defined]
        c._dispatch(p_ka.KeepAlive(keep_alive_id=42))  # type: ignore[attr-defined]

    asyncio.create_task(producer())
    result = await c.wait_for(
        p_ka.KeepAlive,
        timeout=1.0,
        predicate=lambda p: p.keep_alive_id == 42,
    )
    assert result.keep_alive_id == 42


# --- async context manager --------------------------------------------------


@pytest.mark.asyncio
async def test_async_context_manager_disconnect_idempotent() -> None:
    c = Connection.offline(host="127.0.0.1", port=1, username="B")
    async with c:
        # never connected, but exit should not raise
        pass


# --- Reconnected event ----------------------------------------------------


def test_reconnected_dataclass() -> None:
    r = Reconnected(attempts=3, elapsed=2.5)
    assert r.attempts == 3
    assert r.elapsed == 2.5
