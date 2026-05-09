"""Packet `entity_look` (play/clientbound, id 0x2D).

Rotation-only update (no positional change).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x2D


@dataclass(frozen=True, slots=True)
class EntityLook:
    entity_id: int
    yaw: int       # i8 (steps of 360/256)
    pitch: int     # i8
    on_ground: bool


def decode(reader: Reader) -> EntityLook:
    eid = varint.read(reader)
    yaw, pitch = struct.unpack(">bb", reader.read(2))
    og = reader.read(1)[0]
    if og not in (0, 1):
        raise ValueOutOfRange("entity_look.on_ground", og)
    return EntityLook(entity_id=eid, yaw=yaw, pitch=pitch, on_ground=og == 1)


def encode(packet: EntityLook, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    writer.write(struct.pack(">bb", packet.yaw, packet.pitch))
    writer.write(b"\x01" if packet.on_ground else b"\x00")
