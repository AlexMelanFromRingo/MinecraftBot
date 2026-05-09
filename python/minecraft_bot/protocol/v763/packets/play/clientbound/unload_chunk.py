"""Packet `unload_chunk` (play/clientbound, id 0x1E)."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x1E


@dataclass(frozen=True, slots=True)
class UnloadChunk:
    chunk_x: int  # i32
    chunk_z: int  # i32


def decode(reader: Reader) -> UnloadChunk:
    cx, cz = struct.unpack(">ii", reader.read(8))
    return UnloadChunk(chunk_x=cx, chunk_z=cz)


def encode(packet: UnloadChunk, writer: Writer) -> None:
    writer.write(struct.pack(">ii", packet.chunk_x, packet.chunk_z))
