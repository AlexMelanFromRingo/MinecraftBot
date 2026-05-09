"""Packet `abilities` (play/serverbound, id 0x1C).

Client tells the server its flying state (creative-mode toggle).
``flags`` bitfield: 0x02 = flying.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x1C


@dataclass(frozen=True, slots=True)
class Abilities:
    flags: int  # i8


def decode(reader: Reader) -> Abilities:
    f, = struct.unpack(">b", reader.read(1))
    return Abilities(flags=f)


def encode(packet: Abilities, writer: Writer) -> None:
    writer.write(struct.pack(">b", packet.flags))
