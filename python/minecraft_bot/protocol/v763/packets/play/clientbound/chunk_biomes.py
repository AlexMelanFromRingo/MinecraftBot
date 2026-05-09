"""Packet `chunk_biomes` (play/clientbound, id 0x0D).

Server-pushed chunk-biome update for one or more chunks. Each entry has
a packed ``(chunk_x << 32) | (chunk_z & 0xFFFFFFFF)`` long position
followed by a length-prefixed buffer of biome palette + indices.
The buffer payload is opaque to the framework — high-level Bot API
parses it when needed.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x0D


@dataclass(frozen=True, slots=True)
class ChunkBiomeEntry:
    chunk_x: int    # i32
    chunk_z: int    # i32
    data: bytes     # opaque biome buffer


@dataclass(frozen=True, slots=True)
class ChunkBiomes:
    biomes: tuple[ChunkBiomeEntry, ...]


def decode(reader: Reader) -> ChunkBiomes:
    n = varint.read(reader)
    entries: list[ChunkBiomeEntry] = []
    for _ in range(n):
        packed, = struct.unpack(">q", reader.read(8))
        cx = packed >> 32
        # Sign-extend cx
        if cx & (1 << 31):
            cx -= 1 << 32
        cz = packed & 0xFFFFFFFF
        if cz & (1 << 31):
            cz -= 1 << 32
        ln = varint.read(reader)
        data = reader.read(ln)
        entries.append(ChunkBiomeEntry(chunk_x=cx, chunk_z=cz, data=data))
    return ChunkBiomes(biomes=tuple(entries))


def encode(packet: ChunkBiomes, writer: Writer) -> None:
    varint.write(len(packet.biomes), writer)
    for e in packet.biomes:
        packed = ((e.chunk_x & 0xFFFFFFFF) << 32) | (e.chunk_z & 0xFFFFFFFF)
        # Convert unsigned to signed for big-endian i64
        if packed & (1 << 63):
            packed -= 1 << 64
        writer.write(struct.pack(">q", packed))
        varint.write(len(e.data), writer)
        writer.write(e.data)
