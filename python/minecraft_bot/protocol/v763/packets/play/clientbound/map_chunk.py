"""Packet `map_chunk` (play/clientbound, id 0x24).

Chunk Data and Update Light combined packet. Carries a 16x256x16 (or
16x384x16 in 1.18+) chunk's block + biome data, block-entity NBT
records, and full sky/block light arrays.

This is one of the most data-heavy packets. The internal layout uses
a paletted-container scheme that needs a substantial decoder. For
Phase 4 we capture the entire payload as opaque ``data`` (the chunk-x
and chunk-z header are decoded so the bot can dispatch by chunk
location). Structured paletted-container decoding lands in the Bot API
milestone.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x24


@dataclass(frozen=True, slots=True)
class MapChunk:
    chunk_x: int       # i32
    chunk_z: int       # i32
    payload: bytes     # opaque heightmaps + block data + biome data + light


def decode(reader: Reader) -> MapChunk:
    cx, cz = struct.unpack(">ii", reader.read(8))
    pl = reader.read(reader.remaining())
    return MapChunk(chunk_x=cx, chunk_z=cz, payload=pl)


def encode(packet: MapChunk, writer: Writer) -> None:
    writer.write(struct.pack(">ii", packet.chunk_x, packet.chunk_z))
    writer.write(packet.payload)
