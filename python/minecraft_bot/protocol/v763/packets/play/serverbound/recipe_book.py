"""Packet `recipe_book` (play/serverbound, id 0x21).

Recipe-book UI state update.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x21


@dataclass(frozen=True, slots=True)
class RecipeBook:
    book_id: int           # varint, 0=crafting, 1=furnace, 2=blast, 3=smoker
    book_open: bool
    filter_active: bool


def _bool(reader: Reader, name: str) -> bool:
    b = reader.read(1)[0]
    if b not in (0, 1):
        raise ValueOutOfRange(name, b)
    return b == 1


def decode(reader: Reader) -> RecipeBook:
    bid = varint.read(reader)
    bo = _bool(reader, "recipe_book.open")
    fa = _bool(reader, "recipe_book.filter_active")
    return RecipeBook(book_id=bid, book_open=bo, filter_active=fa)


def encode(packet: RecipeBook, writer: Writer) -> None:
    varint.write(packet.book_id, writer)
    writer.write(b"\x01" if packet.book_open else b"\x00")
    writer.write(b"\x01" if packet.filter_active else b"\x00")
