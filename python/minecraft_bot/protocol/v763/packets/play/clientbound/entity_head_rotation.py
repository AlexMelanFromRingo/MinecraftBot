"""Packet `entity_head_rotation` (play/clientbound, id 0x42).

Updates an entity's head yaw independently of body yaw.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x42


@dataclass(frozen=True, slots=True)
class EntityHeadRotation:
    entity_id: int
    head_yaw: int  # i8 (steps of 360/256)


def decode(reader: Reader) -> EntityHeadRotation:
    eid = varint.read(reader)
    yaw, = struct.unpack(">b", reader.read(1))
    return EntityHeadRotation(entity_id=eid, head_yaw=yaw)


def encode(packet: EntityHeadRotation, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    writer.write(struct.pack(">b", packet.head_yaw))
