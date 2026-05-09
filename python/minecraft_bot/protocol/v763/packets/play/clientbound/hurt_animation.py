"""Packet `hurt_animation` (play/clientbound, id 0x21).

Plays the "took damage" knockback animation on an entity. ``yaw`` is
the direction (in degrees) the damage came from.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x21


@dataclass(frozen=True, slots=True)
class HurtAnimation:
    entity_id: int
    yaw: float  # f32, degrees from north


def decode(reader: Reader) -> HurtAnimation:
    eid = varint.read(reader)
    yaw, = struct.unpack(">f", reader.read(4))
    return HurtAnimation(entity_id=eid, yaw=yaw)


def encode(packet: HurtAnimation, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    writer.write(struct.pack(">f", packet.yaw))
