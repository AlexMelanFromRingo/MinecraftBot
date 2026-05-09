"""Packet `query_block_nbt` (play/serverbound, id 0x01).

Asks the server for the NBT of a block-entity at ``location``.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, position, varint

PACKET_ID = 0x01


@dataclass(frozen=True, slots=True)
class QueryBlockNbt:
    transaction_id: int
    location: tuple[int, int, int]


def decode(reader: Reader) -> QueryBlockNbt:
    return QueryBlockNbt(
        transaction_id=varint.read(reader),
        location=position.read(reader),
    )


def encode(packet: QueryBlockNbt, writer: Writer) -> None:
    varint.write(packet.transaction_id, writer)
    position.write(packet.location, writer)
