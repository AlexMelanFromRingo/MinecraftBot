"""Packet `update_time` (play/clientbound, id 0x5E).

Server's authoritative world clock. ``age`` is total ticks since world
creation; ``time`` is ticks-of-day (0 = sunrise; negative ``time`` means
the day-night cycle is paused).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x5E


@dataclass(frozen=True, slots=True)
class UpdateTime:
    age: int   # i64
    time: int  # i64


def decode(reader: Reader) -> UpdateTime:
    age, time = struct.unpack(">qq", reader.read(16))
    return UpdateTime(age=age, time=time)


def encode(packet: UpdateTime, writer: Writer) -> None:
    writer.write(struct.pack(">qq", packet.age, packet.time))
