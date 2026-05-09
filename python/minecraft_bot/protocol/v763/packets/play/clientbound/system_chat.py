"""Packet `system_chat` (play/clientbound, id 0x64).

Server-broadcast chat (not from a player). ``is_action_bar`` selects
whether the message is shown as an action-bar overlay or a normal chat
line.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x64


@dataclass(frozen=True, slots=True)
class SystemChat:
    content: str          # JSON chat component
    is_action_bar: bool


def decode(reader: Reader) -> SystemChat:
    c = string.read(reader)
    b = reader.read(1)[0]
    if b not in (0, 1):
        raise ValueOutOfRange("system_chat.is_action_bar", b)
    return SystemChat(content=c, is_action_bar=b == 1)


def encode(packet: SystemChat, writer: Writer) -> None:
    string.write(packet.content, writer)
    writer.write(b"\x01" if packet.is_action_bar else b"\x00")
