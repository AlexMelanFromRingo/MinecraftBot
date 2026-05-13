"""Packet `edit_book` (play/serverbound, id 0x0E)."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x0E


@dataclass(frozen=True, slots=True)
class EditBook:
    hand: int
    pages: tuple[str, ...]
    title: str | None


def decode(reader: Reader) -> EditBook:
    hand = varint.read(reader)
    n = varint.read(reader)
    pages = tuple(string.read(reader) for _ in range(n))
    present = reader.read(1)[0]
    if present == 1:
        title: str | None = string.read(reader)
    elif present == 0:
        title = None
    else:
        raise ValueOutOfRange("edit_book.title.present", present)
    return EditBook(hand=hand, pages=pages, title=title)


def encode(packet: EditBook, writer: Writer) -> None:
    varint.write(packet.hand, writer)
    varint.write(len(packet.pages), writer)
    for p in packet.pages:
        string.write(p, writer)
    if packet.title is None:
        writer.write(b"\x00")
    else:
        writer.write(b"\x01")
        string.write(packet.title, writer)
