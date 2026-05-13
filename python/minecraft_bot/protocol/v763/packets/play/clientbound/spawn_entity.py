"""Packet `spawn_entity` (play/clientbound, id 0x01).

Generic entity spawn (mobs, items, projectiles, paintings, etc.). Uses
the unified spawn-entity packet introduced in 1.19. ``object_data``
encoding depends on the entity type (entity-specific data; the framework
just passes it through).
"""

from __future__ import annotations

import struct
import uuid as _uuid_stdlib
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.codec import uuid as uuid_codec

PACKET_ID = 0x01


@dataclass(frozen=True, slots=True)
class SpawnEntity:
    entity_id: int
    object_uuid: _uuid_stdlib.UUID
    entity_type: int          # varint, entity registry id
    x: float
    y: float
    z: float
    pitch: int                # i8 (steps of 360/256)
    yaw: int                  # i8
    head_pitch: int           # i8
    object_data: int          # varint, type-specific
    vx: int                   # i16 (1/8000 block/tick units)
    vy: int                   # i16
    vz: int                   # i16


def decode(reader: Reader) -> SpawnEntity:
    eid = varint.read(reader)
    u = uuid_codec.read(reader)
    et = varint.read(reader)
    x, y, z = struct.unpack(">ddd", reader.read(24))
    pitch, yaw, head_pitch = struct.unpack(">bbb", reader.read(3))
    od = varint.read(reader)
    vx, vy, vz = struct.unpack(">hhh", reader.read(6))
    return SpawnEntity(
        entity_id=eid, object_uuid=u, entity_type=et, x=x, y=y, z=z,
        pitch=pitch, yaw=yaw, head_pitch=head_pitch, object_data=od,
        vx=vx, vy=vy, vz=vz,
    )


def encode(packet: SpawnEntity, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    uuid_codec.write(packet.object_uuid, writer)
    varint.write(packet.entity_type, writer)
    writer.write(struct.pack(">ddd", packet.x, packet.y, packet.z))
    writer.write(struct.pack(">bbb", packet.pitch, packet.yaw, packet.head_pitch))
    varint.write(packet.object_data, writer)
    writer.write(struct.pack(">hhh", packet.vx, packet.vy, packet.vz))
