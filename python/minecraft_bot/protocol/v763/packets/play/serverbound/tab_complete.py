"""Packet `tab_complete` (play/serverbound, id 0x09).

Client asks for command-completion suggestions for ``text``. The server
replies via the clientbound :class:`tab_complete` packet using the same
``transaction_id``.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint

PACKET_ID = 0x09


@dataclass(frozen=True, slots=True)
class TabComplete:
    transaction_id: int
    text: str


def decode(reader: Reader) -> TabComplete:
    return TabComplete(
        transaction_id=varint.read(reader),
        text=string.read(reader),
    )


def encode(packet: TabComplete, writer: Writer) -> None:
    varint.write(packet.transaction_id, writer)
    string.write(packet.text, writer)
