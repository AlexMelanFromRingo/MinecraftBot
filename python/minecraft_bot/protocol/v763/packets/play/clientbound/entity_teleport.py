"""Packet `entity_teleport` (play/clientbound, id 0x68).

Absolute position teleport for an entity. Replaces a series of
:class:`RelEntityMove` packets when the cumulative delta would overflow
the i16 range.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x68


@dataclass(frozen=True, slots=True)
class EntityTeleport:
    entity_id: int
    x: float
    y: float
    z: float
    yaw: int       # i8 (steps of 360/256)
    pitch: int     # i8
    on_ground: bool


def decode(reader: Reader) -> EntityTeleport:
    eid = varint.read(reader)
    x, y, z = struct.unpack(">ddd", reader.read(24))
    yaw, pitch = struct.unpack(">bb", reader.read(2))
    og = reader.read(1)[0]
    if og not in (0, 1):
        raise ValueOutOfRange("entity_teleport.on_ground", og)
    return EntityTeleport(entity_id=eid, x=x, y=y, z=z, yaw=yaw, pitch=pitch, on_ground=og == 1)


def encode(packet: EntityTeleport, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    writer.write(struct.pack(">ddd", packet.x, packet.y, packet.z))
    writer.write(struct.pack(">bb", packet.yaw, packet.pitch))
    writer.write(b"\x01" if packet.on_ground else b"\x00")
