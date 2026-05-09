"""Packet `position_look` (play/serverbound, id 0x15)."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x15


@dataclass(frozen=True, slots=True)
class PositionLook:
    x: float
    y: float
    z: float
    yaw: float
    pitch: float
    on_ground: bool


def decode(reader: Reader) -> PositionLook:
    x, y, z = struct.unpack(">ddd", reader.read(24))
    yaw, pitch = struct.unpack(">ff", reader.read(8))
    og = reader.read(1)[0]
    if og not in (0, 1):
        raise ValueOutOfRange("position_look.on_ground", og)
    return PositionLook(x=x, y=y, z=z, yaw=yaw, pitch=pitch, on_ground=og == 1)


def encode(packet: PositionLook, writer: Writer) -> None:
    writer.write(struct.pack(">ddd", packet.x, packet.y, packet.z))
    writer.write(struct.pack(">ff", packet.yaw, packet.pitch))
    writer.write(b"\x01" if packet.on_ground else b"\x00")
