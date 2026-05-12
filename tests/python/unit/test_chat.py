"""Bot.say / Bot.command unit tests (T081)."""

from __future__ import annotations

import asyncio
from typing import Any

from minecraft_bot.bot import Bot
from minecraft_bot.events import ChatMessageEvent
from minecraft_bot.protocol.v763.packets.play.serverbound.chat_command import (
    ChatCommand,
)
from minecraft_bot.protocol.v763.packets.play.serverbound.chat_message import (
    ChatMessage,
)


def _bot_with_capture() -> tuple[Bot, list]:
    bot = Bot.offline("h", 25565, "t")
    sent: list = []

    async def fake_send(p: Any) -> None:
        sent.append(p)

    bot._conn.send = fake_send   # type: ignore[assignment]
    return bot, sent


def test_say_emits_chat_message_with_text() -> None:
    bot, sent = _bot_with_capture()
    asyncio.run(bot.say("hello world"))
    msgs = [p for p in sent if isinstance(p, ChatMessage)]
    assert msgs, f"no ChatMessage sent (got {[type(p).__name__ for p in sent]})"
    assert msgs[0].message == "hello world"
    assert msgs[0].timestamp > 0
    assert msgs[0].signature is None
    assert msgs[0].acknowledged == b"\x00\x00\x00"


def test_command_strips_leading_slash() -> None:
    bot, sent = _bot_with_capture()
    asyncio.run(bot.command("/give @s minecraft:diamond"))
    cmds = [p for p in sent if isinstance(p, ChatCommand)]
    assert cmds and cmds[0].command == "give @s minecraft:diamond"


def test_command_without_slash_passed_through() -> None:
    bot, sent = _bot_with_capture()
    asyncio.run(bot.command("tp 0 64 0"))
    cmds = [p for p in sent if isinstance(p, ChatCommand)]
    assert cmds[0].command == "tp 0 64 0"


def test_command_payload_has_expected_length() -> None:
    """Payload = i64 ts + i64 salt + varint sigs(0) + varint count(0)
    + 3 bytes ack = 21 bytes."""
    bot, sent = _bot_with_capture()
    asyncio.run(bot.command("test"))
    cmds = [p for p in sent if isinstance(p, ChatCommand)]
    assert len(cmds[0].payload) == 21


def test_system_chat_routes_to_event() -> None:
    """Clientbound system_chat → ChatMessageEvent emitted."""
    from minecraft_bot.protocol.v763.packets.play.clientbound.system_chat import (
        SystemChat,
    )
    bot = Bot.offline("h", 25565, "t")
    received: list[ChatMessageEvent] = []

    @bot.on(ChatMessageEvent)
    def handler(e):
        received.append(e)

    bot._on_system_chat(SystemChat(content='{"text":"Server boot"}', is_action_bar=False))
    assert len(received) == 1
    assert received[0].chat_type == "system"
    assert "Server boot" in received[0].raw


def test_profileless_chat_routes_to_event() -> None:
    from minecraft_bot.protocol.v763.packets.play.clientbound.profileless_chat import (
        ProfilelessChat,
    )
    bot = Bot.offline("h", 25565, "t")
    received: list[ChatMessageEvent] = []

    @bot.on(ChatMessageEvent)
    def handler(e):
        received.append(e)

    bot._on_profileless_chat(ProfilelessChat(
        message='{"text":"npc says hi"}', chat_type=0,
        name='{"text":"NPC"}', target=None,
    ))
    assert len(received) == 1
    assert received[0].chat_type == "profileless"
