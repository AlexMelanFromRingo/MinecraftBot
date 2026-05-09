"""Packet `entity_status` (play/clientbound, id 0x1C).

A single-byte event for an entity (eat-particles, jump-particles, etc.).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x1C


@dataclass(frozen=True, slots=True)
class EntityStatus:
    entity_id: int  # i32
    status: int     # i8


def decode(reader: Reader) -> EntityStatus:
    eid, = struct.unpack(">i", reader.read(4))
    st, = struct.unpack(">b", reader.read(1))
    return EntityStatus(entity_id=eid, status=st)


def encode(packet: EntityStatus, writer: Writer) -> None:
    writer.write(struct.pack(">ib", packet.entity_id, packet.status))
