"""Packet `use_item` (play/serverbound, id 0x32).

Player right-clicked into the air (no targeted block). ``hand``: 0=main, 1=off.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x32


@dataclass(frozen=True, slots=True)
class UseItem:
    hand: int       # varint
    sequence: int   # varint


def decode(reader: Reader) -> UseItem:
    return UseItem(hand=varint.read(reader), sequence=varint.read(reader))


def encode(packet: UseItem, writer: Writer) -> None:
    varint.write(packet.hand, writer)
    varint.write(packet.sequence, writer)
