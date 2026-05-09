"""Packet `collect` (play/clientbound, id 0x67).

Plays the "item picked up" animation: the collected entity flies into
the collector. Used for items, XP orbs, and arrows being picked up.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x67


@dataclass(frozen=True, slots=True)
class Collect:
    collected_entity_id: int   # varint
    collector_entity_id: int   # varint
    pickup_item_count: int     # varint


def decode(reader: Reader) -> Collect:
    cd = varint.read(reader)
    cr = varint.read(reader)
    cnt = varint.read(reader)
    return Collect(collected_entity_id=cd, collector_entity_id=cr, pickup_item_count=cnt)


def encode(packet: Collect, writer: Writer) -> None:
    varint.write(packet.collected_entity_id, writer)
    varint.write(packet.collector_entity_id, writer)
    varint.write(packet.pickup_item_count, writer)
