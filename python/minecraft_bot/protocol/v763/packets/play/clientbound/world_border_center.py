"""Packet `world_border_center` (play/clientbound, id 0x47).

Recentre the world-border square on these world coordinates.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x47


@dataclass(frozen=True, slots=True)
class WorldBorderCenter:
    x: float
    z: float


def decode(reader: Reader) -> WorldBorderCenter:
    x, z = struct.unpack(">dd", reader.read(16))
    return WorldBorderCenter(x=x, z=z)


def encode(packet: WorldBorderCenter, writer: Writer) -> None:
    writer.write(struct.pack(">dd", packet.x, packet.z))
