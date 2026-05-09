"""Packet `open_book` (play/clientbound, id 0x2F).

Triggers the client to open the written-book viewer for the book held
in ``hand``: 0 = main hand, 1 = off-hand.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x2F


@dataclass(frozen=True, slots=True)
class OpenBook:
    hand: int  # varint: 0 = MAIN_HAND, 1 = OFF_HAND


def decode(reader: Reader) -> OpenBook:
    return OpenBook(hand=varint.read(reader))


def encode(packet: OpenBook, writer: Writer) -> None:
    varint.write(packet.hand, writer)
