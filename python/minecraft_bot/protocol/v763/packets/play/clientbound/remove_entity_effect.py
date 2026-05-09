"""Packet `remove_entity_effect` (play/clientbound, id 0x3F).

Removes a status effect (potion effect) from an entity.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x3F


@dataclass(frozen=True, slots=True)
class RemoveEntityEffect:
    entity_id: int   # varint
    effect_id: int   # varint, registry id of the effect


def decode(reader: Reader) -> RemoveEntityEffect:
    eid = varint.read(reader)
    eff = varint.read(reader)
    return RemoveEntityEffect(entity_id=eid, effect_id=eff)


def encode(packet: RemoveEntityEffect, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    varint.write(packet.effect_id, writer)
