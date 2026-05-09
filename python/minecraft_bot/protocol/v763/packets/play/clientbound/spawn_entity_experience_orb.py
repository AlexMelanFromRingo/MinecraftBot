"""Packet `spawn_entity_experience_orb` (play/clientbound, id 0x02)."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x02


@dataclass(frozen=True, slots=True)
class SpawnEntityExperienceOrb:
    entity_id: int   # varint
    x: float
    y: float
    z: float
    count: int       # i16


def decode(reader: Reader) -> SpawnEntityExperienceOrb:
    eid = varint.read(reader)
    x, y, z = struct.unpack(">ddd", reader.read(24))
    (count,) = struct.unpack(">h", reader.read(2))
    return SpawnEntityExperienceOrb(entity_id=eid, x=x, y=y, z=z, count=count)


def encode(packet: SpawnEntityExperienceOrb, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    writer.write(struct.pack(">ddd", packet.x, packet.y, packet.z))
    writer.write(struct.pack(">h", packet.count))
