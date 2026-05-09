"""Packet `update_light` (play/clientbound, id 0x27).

Standalone light-update packet (separate from map_chunk for incremental
lighting changes). Carries a chunk position plus several BitSets and
length-prefixed arrays of nibble light data.

Phase 4 captures the payload as opaque bytes after the chunk header;
structured decode lives in the Bot API milestone.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x27


@dataclass(frozen=True, slots=True)
class UpdateLight:
    chunk_x: int   # varint
    chunk_z: int   # varint
    payload: bytes


def decode(reader: Reader) -> UpdateLight:
    cx = varint.read(reader)
    cz = varint.read(reader)
    pl = reader.read(reader.remaining())
    return UpdateLight(chunk_x=cx, chunk_z=cz, payload=pl)


def encode(packet: UpdateLight, writer: Writer) -> None:
    varint.write(packet.chunk_x, writer)
    varint.write(packet.chunk_z, writer)
    writer.write(packet.payload)
