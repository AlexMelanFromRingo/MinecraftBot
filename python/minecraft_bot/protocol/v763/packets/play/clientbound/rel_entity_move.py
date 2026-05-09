"""Packet `rel_entity_move` (play/clientbound, id 0x2B).

Delta movement of an entity. ``dx``/``dy``/``dz`` are encoded as
``current * 32 * 128 - prev * 32 * 128`` per the protocol's fixed-point
deltas — multiply by ``1/(32*128) = 1/4096`` to get the world-space
delta. Used for small movements (under 8 blocks); larger jumps come
through :class:`~minecraft_bot.protocol.v763.packets.play.clientbound.entity_teleport.EntityTeleport`.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x2B


@dataclass(frozen=True, slots=True)
class RelEntityMove:
    entity_id: int
    dx: int      # i16 fixed-point (1/4096 block units)
    dy: int      # i16
    dz: int      # i16
    on_ground: bool


def decode(reader: Reader) -> RelEntityMove:
    eid = varint.read(reader)
    dx, dy, dz = struct.unpack(">hhh", reader.read(6))
    og = reader.read(1)[0]
    if og not in (0, 1):
        raise ValueOutOfRange("rel_entity_move.on_ground", og)
    return RelEntityMove(entity_id=eid, dx=dx, dy=dy, dz=dz, on_ground=og == 1)


def encode(packet: RelEntityMove, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    writer.write(struct.pack(">hhh", packet.dx, packet.dy, packet.dz))
    writer.write(b"\x01" if packet.on_ground else b"\x00")
