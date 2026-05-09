"""Packet `entity_destroy` (play/clientbound, id 0x3E).

Removes one or more entities from the client's tracking. Sent in
batches when entities go out of view distance.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x3E


@dataclass(frozen=True, slots=True)
class EntityDestroy:
    entity_ids: tuple[int, ...]  # varint count + varint ids


def decode(reader: Reader) -> EntityDestroy:
    n = varint.read(reader)
    ids = tuple(varint.read(reader) for _ in range(n))
    return EntityDestroy(entity_ids=ids)


def encode(packet: EntityDestroy, writer: Writer) -> None:
    varint.write(len(packet.entity_ids), writer)
    for eid in packet.entity_ids:
        varint.write(eid, writer)
