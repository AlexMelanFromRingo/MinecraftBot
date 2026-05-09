"""Packet `multi_block_change` (play/clientbound, id 0x43).

Updates many blocks within a single 16x16x16 chunk section in one
packet. ``chunk_coordinates`` is a 64-bit packed bitfield::

    [22 bits signed x | 22 bits signed z | 20 bits signed y]

Each ``records`` entry is a packed VarLong (encoded here as a varint
stream of long-style values, but minecraft-data calls them varints in
the schema; the in-protocol units are 22+8 = 30 bit packed
``(block_state_id << 12) | (rel_pos & 0xFFF)``).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x43


def _sign_extend(value: int, bits: int) -> int:
    mask = (1 << bits) - 1
    value &= mask
    if value & (1 << (bits - 1)):
        value -= 1 << bits
    return value


@dataclass(frozen=True, slots=True)
class MultiBlockChange:
    chunk_section_x: int   # 22-bit signed
    chunk_section_z: int   # 22-bit signed
    chunk_section_y: int   # 20-bit signed
    records: tuple[int, ...]   # packed (block_state << 12) | rel_xyz


def decode(reader: Reader) -> MultiBlockChange:
    packed, = struct.unpack(">q", reader.read(8))
    cy = _sign_extend(packed & 0xFFFFF, 20)
    cz = _sign_extend((packed >> 20) & 0x3FFFFF, 22)
    cx = _sign_extend((packed >> 42) & 0x3FFFFF, 22)
    n = varint.read(reader)
    recs = tuple(varint.read(reader) for _ in range(n))
    return MultiBlockChange(
        chunk_section_x=cx, chunk_section_z=cz, chunk_section_y=cy, records=recs,
    )


def encode(packet: MultiBlockChange, writer: Writer) -> None:
    cx = packet.chunk_section_x & 0x3FFFFF
    cz = packet.chunk_section_z & 0x3FFFFF
    cy = packet.chunk_section_y & 0xFFFFF
    packed = (cx << 42) | (cz << 20) | cy
    if packed & (1 << 63):
        packed -= 1 << 64
    writer.write(struct.pack(">q", packed))
    varint.write(len(packet.records), writer)
    for r in packet.records:
        varint.write(r, writer)
