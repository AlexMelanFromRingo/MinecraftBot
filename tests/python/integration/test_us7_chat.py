"""US7 — Chat & commands (live integration, T082).

Bot says a unique message and waits to receive its echo (via a
broadcast or system message). On Paper with offline-mode any /say or
/me from another op is broadcast back.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from minecraft_bot.bot import Bot
from minecraft_bot.events import ChatMessageEvent

pytestmark = pytest.mark.live


ARENA_CX, ARENA_CY, ARENA_CZ = 10000, 200, 10000


async def _spawn_on_arena(bot: Bot, name: str) -> None:
    await bot.connect()
    await asyncio.sleep(1.5)
    await bot.command(f"tp {name} {ARENA_CX} {ARENA_CY} {ARENA_CZ}")
    await asyncio.sleep(3.0)


def _contains_nonce(event: ChatMessageEvent, nonce: str) -> bool:
    """Check if the nonce appears in either the textual fields or the
    hex-encoded payload (player_chat raw is the binary payload hex)."""
    nonce_hex = nonce.encode("utf-8").hex()
    return (
        nonce in event.raw
        or nonce in event.message
        or nonce_hex in event.raw
    )


async def test_command_response_arrives_as_chat_event(live_server) -> None:
    """`/say <message>` is broadcast back — verify ChatMessageEvent fires
    and the message is detectable in either system_chat (JSON) or
    player_chat (hex payload) raw."""
    bot = Bot.offline(live_server.host, live_server.port, "TestBot1")
    received: list[ChatMessageEvent] = []

    @bot.on(ChatMessageEvent)
    def handler(e):
        received.append(e)

    await _spawn_on_arena(bot, "TestBot1")
    try:
        nonce = f"ping-{int(time.time())}"
        await bot.command(f"say {nonce}")
        await asyncio.sleep(2.0)
        matched = [e for e in received if _contains_nonce(e, nonce)]
        assert matched, (
            f"didn't see broadcast of {nonce!r}; got {len(received)} events"
        )
    finally:
        await bot.disconnect()
    await asyncio.sleep(1.0)


async def test_say_message_is_broadcast(live_server) -> None:
    """Verify Bot.say() reaches other connected bots — connect TWO
    bots, have one say, watch the other receive."""
    listener = Bot.offline(live_server.host, live_server.port, "TestBot2")
    received: list[ChatMessageEvent] = []

    @listener.on(ChatMessageEvent)
    def handler(e):
        received.append(e)

    await _spawn_on_arena(listener, "TestBot2")
    speaker = Bot.offline(live_server.host, live_server.port, "TestBot3")
    await _spawn_on_arena(speaker, "TestBot3")
    try:
        nonce = f"hello-{int(time.time())}"
        await speaker.say(nonce)
        await asyncio.sleep(2.0)
        matched = [e for e in received if _contains_nonce(e, nonce)]
        assert matched, (
            f"TestBot2 didn't see say from TestBot3; got {len(received)} events"
        )
    finally:
        await speaker.disconnect()
        await listener.disconnect()
    await asyncio.sleep(1.0)
