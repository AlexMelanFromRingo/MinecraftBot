"""Packet `generate_structure` (play/serverbound, id 0x11). Op-only."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, position, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x11


@dataclass(frozen=True, slots=True)
class GenerateStructure:
    location: tuple[int, int, int]
    levels: int
    keep_jigsaws: bool


def decode(reader: Reader) -> GenerateStructure:
    loc = position.read(reader)
    lv = varint.read(reader)
    kj = reader.read(1)[0]
    if kj not in (0, 1):
        raise ValueOutOfRange("generate_structure.keep_jigsaws", kj)
    return GenerateStructure(location=loc, levels=lv, keep_jigsaws=kj == 1)


def encode(packet: GenerateStructure, writer: Writer) -> None:
    position.write(packet.location, writer)
    varint.write(packet.levels, writer)
    writer.write(b"\x01" if packet.keep_jigsaws else b"\x00")
