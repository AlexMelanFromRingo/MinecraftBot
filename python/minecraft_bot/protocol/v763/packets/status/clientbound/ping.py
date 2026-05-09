"""Packet `ping` (status/clientbound, id 0x01).

The server's pong reply to a serverbound ping. ``time`` echoes the
i64 the client sent so latency can be measured.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x01


@dataclass(frozen=True, slots=True)
class Ping:
    time: int  # i64


def decode(reader: Reader) -> Ping:
    return Ping(time=struct.unpack(">q", reader.read(8))[0])


def encode(packet: Ping, writer: Writer) -> None:
    writer.write(struct.pack(">q", packet.time))
