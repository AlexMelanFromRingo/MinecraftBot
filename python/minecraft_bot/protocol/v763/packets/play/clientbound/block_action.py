"""Packet `block_action` (play/clientbound, id 0x09).

Sent for note blocks, pistons, etc.; meaning of ``byte1`` and ``byte2``
depends on ``block_type``.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, position, varint

PACKET_ID = 0x09


@dataclass(frozen=True, slots=True)
class BlockAction:
    location: tuple[int, int, int]
    byte1: int       # u8
    byte2: int       # u8
    block_type: int  # varint (block-state ID)


def decode(reader: Reader) -> BlockAction:
    loc = position.read(reader)
    b1 = reader.read(1)[0]
    b2 = reader.read(1)[0]
    bt = varint.read(reader)
    return BlockAction(location=loc, byte1=b1, byte2=b2, block_type=bt)


def encode(packet: BlockAction, writer: Writer) -> None:
    position.write(packet.location, writer)
    writer.write(bytes([packet.byte1 & 0xFF, packet.byte2 & 0xFF]))
    varint.write(packet.block_type, writer)
