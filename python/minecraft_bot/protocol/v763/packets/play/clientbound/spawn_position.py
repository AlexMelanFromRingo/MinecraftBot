"""Packet `spawn_position` (play/clientbound, id 0x50).

Sets the world's spawn point (used by `/spawn`, F3 compass, respawn
fallback). ``angle`` is the spawn yaw in degrees (added in 1.18).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, position

PACKET_ID = 0x50


@dataclass(frozen=True, slots=True)
class SpawnPosition:
    location: tuple[int, int, int]
    angle: float  # f32, degrees


def decode(reader: Reader) -> SpawnPosition:
    loc = position.read(reader)
    a, = struct.unpack(">f", reader.read(4))
    return SpawnPosition(location=loc, angle=a)


def encode(packet: SpawnPosition, writer: Writer) -> None:
    position.write(packet.location, writer)
    writer.write(struct.pack(">f", packet.angle))
