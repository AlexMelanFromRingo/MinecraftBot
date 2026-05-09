"""Packet `ping` (status/serverbound, id 0x01).

Client-initiated ping; server echoes ``time`` back via the clientbound
``ping`` packet. Used to measure latency in the status flow.
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
