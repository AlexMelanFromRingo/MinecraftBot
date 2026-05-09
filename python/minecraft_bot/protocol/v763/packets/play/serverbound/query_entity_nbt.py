"""Packet `query_entity_nbt` (play/serverbound, id 0x0F)."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x0F


@dataclass(frozen=True, slots=True)
class QueryEntityNbt:
    transaction_id: int
    entity_id: int


def decode(reader: Reader) -> QueryEntityNbt:
    return QueryEntityNbt(
        transaction_id=varint.read(reader),
        entity_id=varint.read(reader),
    )


def encode(packet: QueryEntityNbt, writer: Writer) -> None:
    varint.write(packet.transaction_id, writer)
    varint.write(packet.entity_id, writer)
