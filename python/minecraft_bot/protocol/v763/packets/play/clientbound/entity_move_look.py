"""Packet `entity_move_look` (play/clientbound, id 0x2C).

Combined relative move + rotation update. Same fixed-point semantics
as :class:`~minecraft_bot.protocol.v763.packets.play.clientbound.rel_entity_move.RelEntityMove`.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x2C


@dataclass(frozen=True, slots=True)
class EntityMoveLook:
    entity_id: int
    dx: int
    dy: int
    dz: int
    yaw: int
    pitch: int
    on_ground: bool


def decode(reader: Reader) -> EntityMoveLook:
    eid = varint.read(reader)
    dx, dy, dz, yaw, pitch = struct.unpack(">hhhbb", reader.read(8))
    og = reader.read(1)[0]
    if og not in (0, 1):
        raise ValueOutOfRange("entity_move_look.on_ground", og)
    return EntityMoveLook(entity_id=eid, dx=dx, dy=dy, dz=dz, yaw=yaw, pitch=pitch, on_ground=og == 1)


def encode(packet: EntityMoveLook, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    writer.write(struct.pack(">hhhbb", packet.dx, packet.dy, packet.dz,
                              packet.yaw, packet.pitch))
    writer.write(b"\x01" if packet.on_ground else b"\x00")
