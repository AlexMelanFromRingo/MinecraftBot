"""Packet `named_entity_spawn` (play/clientbound, id 0x03).

Spawn (other) Player entity. ``yaw`` and ``pitch`` are i8 in
"steps of 360/256" — multiply by 360/256 to get degrees.
"""

from __future__ import annotations

import struct
import uuid as _uuid_stdlib
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.codec import uuid as uuid_codec

PACKET_ID = 0x03


@dataclass(frozen=True, slots=True)
class NamedEntitySpawn:
    entity_id: int
    player_uuid: _uuid_stdlib.UUID
    x: float
    y: float
    z: float
    yaw: int    # i8 (steps of 360/256)
    pitch: int  # i8


def decode(reader: Reader) -> NamedEntitySpawn:
    eid = varint.read(reader)
    u = uuid_codec.read(reader)
    x, y, z = struct.unpack(">ddd", reader.read(24))
    yaw, pitch = struct.unpack(">bb", reader.read(2))
    return NamedEntitySpawn(entity_id=eid, player_uuid=u, x=x, y=y, z=z, yaw=yaw, pitch=pitch)


def encode(packet: NamedEntitySpawn, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    uuid_codec.write(packet.player_uuid, writer)
    writer.write(struct.pack(">ddd", packet.x, packet.y, packet.z))
    writer.write(struct.pack(">bb", packet.yaw, packet.pitch))
