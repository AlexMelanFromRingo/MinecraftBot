"""Packet `block_place` (play/serverbound, id 0x31).

Player right-clicked while looking at a block face. ``hand``: 0=main, 1=off.
``direction``: face id 0..5 (down/up/north/south/west/east). ``cursor_*``
is the click position within the face (0..1).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, position, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x31


@dataclass(frozen=True, slots=True)
class BlockPlace:
    hand: int                       # varint
    location: tuple[int, int, int]
    direction: int                  # varint (face)
    cursor_x: float                 # f32
    cursor_y: float
    cursor_z: float
    inside_block: bool
    sequence: int                   # varint


def decode(reader: Reader) -> BlockPlace:
    h = varint.read(reader)
    loc = position.read(reader)
    d = varint.read(reader)
    cx, cy, cz = struct.unpack(">fff", reader.read(12))
    ib = reader.read(1)[0]
    if ib not in (0, 1):
        raise ValueOutOfRange("block_place.inside_block", ib)
    seq = varint.read(reader)
    return BlockPlace(hand=h, location=loc, direction=d,
                      cursor_x=cx, cursor_y=cy, cursor_z=cz,
                      inside_block=ib == 1, sequence=seq)


def encode(packet: BlockPlace, writer: Writer) -> None:
    varint.write(packet.hand, writer)
    position.write(packet.location, writer)
    varint.write(packet.direction, writer)
    writer.write(struct.pack(">fff", packet.cursor_x, packet.cursor_y, packet.cursor_z))
    writer.write(b"\x01" if packet.inside_block else b"\x00")
    varint.write(packet.sequence, writer)
