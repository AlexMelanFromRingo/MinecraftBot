"""Packet `action_bar` (play/clientbound, id 0x46).

Sets the text shown above the hotbar (the "action bar"). ``text`` is a
JSON chat component.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string

PACKET_ID = 0x46


@dataclass(frozen=True, slots=True)
class ActionBar:
    text: str  # JSON chat component


def decode(reader: Reader) -> ActionBar:
    return ActionBar(text=string.read(reader))


def encode(packet: ActionBar, writer: Writer) -> None:
    string.write(packet.text, writer)
