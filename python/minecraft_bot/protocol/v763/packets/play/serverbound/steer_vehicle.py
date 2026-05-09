"""Packet `steer_vehicle` (play/serverbound, id 0x1F)."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x1F


@dataclass(frozen=True, slots=True)
class SteerVehicle:
    sideways: float  # f32
    forward: float   # f32
    flags: int       # u8 (0x01 jump, 0x02 unmount)


def decode(reader: Reader) -> SteerVehicle:
    sw, fw = struct.unpack(">ff", reader.read(8))
    fl = reader.read(1)[0]
    return SteerVehicle(sideways=sw, forward=fw, flags=fl)


def encode(packet: SteerVehicle, writer: Writer) -> None:
    writer.write(struct.pack(">ff", packet.sideways, packet.forward))
    writer.write(bytes([packet.flags & 0xFF]))
