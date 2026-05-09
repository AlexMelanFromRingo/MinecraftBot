"""Packet `entity_velocity` (play/clientbound, id 0x54).

Velocity vector (``vec3i16`` in minecraft-data) — three i16 values
encoded as ``actual_velocity * 8000`` per the protocol's fixed-point.
Multiply by ``1/8000`` to get blocks-per-tick.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x54


@dataclass(frozen=True, slots=True)
class EntityVelocity:
    entity_id: int
    vx: int  # i16 (1/8000 block/tick units)
    vy: int  # i16
    vz: int  # i16


def decode(reader: Reader) -> EntityVelocity:
    eid = varint.read(reader)
    vx, vy, vz = struct.unpack(">hhh", reader.read(6))
    return EntityVelocity(entity_id=eid, vx=vx, vy=vy, vz=vz)


def encode(packet: EntityVelocity, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    writer.write(struct.pack(">hhh", packet.vx, packet.vy, packet.vz))
