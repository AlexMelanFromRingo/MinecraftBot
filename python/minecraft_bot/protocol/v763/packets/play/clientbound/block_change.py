"""Packet `block_change` (play/clientbound, id 0x0A).

Single-block update: ``location`` is the world position; ``block_state_id``
is the new block-state ID.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, position, varint

PACKET_ID = 0x0A


@dataclass(frozen=True, slots=True)
class BlockChange:
    location: tuple[int, int, int]
    block_state_id: int    # varint


def decode(reader: Reader) -> BlockChange:
    loc = position.read(reader)
    bid = varint.read(reader)
    return BlockChange(location=loc, block_state_id=bid)


def encode(packet: BlockChange, writer: Writer) -> None:
    position.write(packet.location, writer)
    varint.write(packet.block_state_id, writer)
