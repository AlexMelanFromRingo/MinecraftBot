"""Packet `position` (play/serverbound, id 0x14).

Player movement-only update (no rotation).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x14


@dataclass(frozen=True, slots=True)
class Position:
    x: float
    y: float
    z: float
    on_ground: bool


def decode(reader: Reader) -> Position:
    x, y, z = struct.unpack(">ddd", reader.read(24))
    og = reader.read(1)[0]
    if og not in (0, 1):
        raise ValueOutOfRange("position.on_ground", og)
    return Position(x=x, y=y, z=z, on_ground=og == 1)


def encode(packet: Position, writer: Writer) -> None:
    writer.write(struct.pack(">ddd", packet.x, packet.y, packet.z))
    writer.write(b"\x01" if packet.on_ground else b"\x00")
