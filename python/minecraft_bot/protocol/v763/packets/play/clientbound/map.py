"""Packet `map` (play/clientbound, id 0x29).

Updates the contents of an in-game map item (cartographer maps).
Several optional sections control which fields follow.

Phase 4 captures the trailing payload as opaque bytes after the
``map_id`` and ``scale`` header.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x29


@dataclass(frozen=True, slots=True)
class Map:
    map_id: int        # varint
    scale: int         # i8
    payload: bytes     # opaque tail (locked, decorations, color update)


def decode(reader: Reader) -> Map:
    mid = varint.read(reader)
    scale, = struct.unpack(">b", reader.read(1))
    pl = reader.read(reader.remaining())
    return Map(map_id=mid, scale=scale, payload=pl)


def encode(packet: Map, writer: Writer) -> None:
    varint.write(packet.map_id, writer)
    writer.write(struct.pack(">b", packet.scale))
    writer.write(packet.payload)
