"""Packet `attach_entity` (play/clientbound, id 0x53).

Leashes an entity to another (or detaches when ``vehicle_id == -1``).
Mostly for mobs leashed to fence posts.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x53


@dataclass(frozen=True, slots=True)
class AttachEntity:
    entity_id: int   # i32 — the leashed entity
    vehicle_id: int  # i32 — the holder; -1 = detach


def decode(reader: Reader) -> AttachEntity:
    eid, vid = struct.unpack(">ii", reader.read(8))
    return AttachEntity(entity_id=eid, vehicle_id=vid)


def encode(packet: AttachEntity, writer: Writer) -> None:
    writer.write(struct.pack(">ii", packet.entity_id, packet.vehicle_id))
