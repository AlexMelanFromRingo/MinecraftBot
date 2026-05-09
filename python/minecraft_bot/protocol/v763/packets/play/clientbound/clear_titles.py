"""Packet `clear_titles` (play/clientbound, id 0x0E).

Tells the client to clear (or fully reset) any displayed title.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x0E


@dataclass(frozen=True, slots=True)
class ClearTitles:
    reset: bool


def decode(reader: Reader) -> ClearTitles:
    b = reader.read(1)[0]
    if b not in (0, 1):
        raise ValueOutOfRange("clear_titles.reset", b)
    return ClearTitles(reset=b == 1)


def encode(packet: ClearTitles, writer: Writer) -> None:
    writer.write(b"\x01" if packet.reset else b"\x00")
