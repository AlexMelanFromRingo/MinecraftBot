"""Packet `experience` (play/clientbound, id 0x56).

Updates the player's XP bar.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x56


@dataclass(frozen=True, slots=True)
class Experience:
    experience_bar: float  # 0.0..1.0
    level: int             # varint
    total_experience: int  # varint, total XP earned


def decode(reader: Reader) -> Experience:
    bar, = struct.unpack(">f", reader.read(4))
    lvl = varint.read(reader)
    total = varint.read(reader)
    return Experience(experience_bar=bar, level=lvl, total_experience=total)


def encode(packet: Experience, writer: Writer) -> None:
    writer.write(struct.pack(">f", packet.experience_bar))
    varint.write(packet.level, writer)
    varint.write(packet.total_experience, writer)
