"""Packet `vehicle_move` (play/serverbound, id 0x18)."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x18


@dataclass(frozen=True, slots=True)
class VehicleMove:
    x: float
    y: float
    z: float
    yaw: float
    pitch: float


def decode(reader: Reader) -> VehicleMove:
    x, y, z = struct.unpack(">ddd", reader.read(24))
    yaw, pitch = struct.unpack(">ff", reader.read(8))
    return VehicleMove(x=x, y=y, z=z, yaw=yaw, pitch=pitch)


def encode(packet: VehicleMove, writer: Writer) -> None:
    writer.write(struct.pack(">ddd", packet.x, packet.y, packet.z))
    writer.write(struct.pack(">ff", packet.yaw, packet.pitch))
