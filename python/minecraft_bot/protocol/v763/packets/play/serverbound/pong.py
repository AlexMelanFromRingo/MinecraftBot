"""Packet `pong` (play/serverbound, id 0x20).

Client's reply to a clientbound :class:`ping`. Echoes ``id``.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x20


@dataclass(frozen=True, slots=True)
class Pong:
    id: int  # i32


def decode(reader: Reader) -> Pong:
    pid, = struct.unpack(">i", reader.read(4))
    return Pong(id=pid)


def encode(packet: Pong, writer: Writer) -> None:
    writer.write(struct.pack(">i", packet.id))
