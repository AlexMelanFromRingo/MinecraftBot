"""Packet `abilities` (play/clientbound, id 0x34).

Player ability flags + speed multipliers. ``flags`` is a bitfield::

    0x01  invulnerable
    0x02  flying
    0x04  allow flying
    0x08  creative mode (instant break)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x34


@dataclass(frozen=True, slots=True)
class Abilities:
    flags: int           # i8 bitfield
    flying_speed: float  # f32; default 0.05
    walking_speed: float # f32; default 0.1


def decode(reader: Reader) -> Abilities:
    flags, = struct.unpack(">b", reader.read(1))
    fly, walk = struct.unpack(">ff", reader.read(8))
    return Abilities(flags=flags, flying_speed=fly, walking_speed=walk)


def encode(packet: Abilities, writer: Writer) -> None:
    writer.write(struct.pack(">b", packet.flags))
    writer.write(struct.pack(">ff", packet.flying_speed, packet.walking_speed))
