"""Packet `tile_entity_data` (play/clientbound, id 0x08).

Updates a block-entity's NBT (signs, beds, banners, etc.). ``action``
is the block-entity-update event code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from minecraft_bot.codec import Reader, Writer, nbt, position, varint

PACKET_ID = 0x08


@dataclass(frozen=True, slots=True)
class TileEntityData:
    location: tuple[int, int, int]
    action: int                     # varint
    nbt_data: Optional[nbt.NbtTag]  # may be None (single TAG_End byte)


def decode(reader: Reader) -> TileEntityData:
    loc = position.read(reader)
    act = varint.read(reader)
    tag = nbt.read(reader)
    return TileEntityData(location=loc, action=act, nbt_data=tag)


def encode(packet: TileEntityData, writer: Writer) -> None:
    position.write(packet.location, writer)
    varint.write(packet.action, writer)
    nbt.write(packet.nbt_data, writer)
