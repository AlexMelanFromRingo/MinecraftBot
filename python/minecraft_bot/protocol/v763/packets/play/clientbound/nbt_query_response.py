"""Packet `nbt_query_response` (play/clientbound, id 0x66).

Server's reply to a serverbound ``query_block_nbt`` or
``query_entity_nbt``. ``nbt`` is the queried NBT or ``None`` if the
target had none.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from minecraft_bot.codec import Reader, Writer, nbt, varint

PACKET_ID = 0x66


@dataclass(frozen=True, slots=True)
class NbtQueryResponse:
    transaction_id: int            # varint, matches the request
    nbt: Optional[nbt.NbtTag]


def decode(reader: Reader) -> NbtQueryResponse:
    tid = varint.read(reader)
    tag = nbt.read(reader)
    return NbtQueryResponse(transaction_id=tid, nbt=tag)


def encode(packet: NbtQueryResponse, writer: Writer) -> None:
    varint.write(packet.transaction_id, writer)
    nbt.write(packet.nbt, writer)
