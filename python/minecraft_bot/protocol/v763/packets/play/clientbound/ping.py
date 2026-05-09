"""Packet `ping` (play/clientbound, id 0x32).

Server-side latency probe. Client must immediately send back a serverbound
``pong`` echoing ``id``.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x32


@dataclass(frozen=True, slots=True)
class Ping:
    id: int  # i32


def decode(reader: Reader) -> Ping:
    pid, = struct.unpack(">i", reader.read(4))
    return Ping(id=pid)


def encode(packet: Ping, writer: Writer) -> None:
    writer.write(struct.pack(">i", packet.id))
