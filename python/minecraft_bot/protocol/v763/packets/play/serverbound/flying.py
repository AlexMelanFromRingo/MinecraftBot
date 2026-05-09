"""Packet `flying` (play/serverbound, id 0x17).

"Player Movement" / on-ground only signal. Sent every tick by vanilla
clients to keep the server informed of the on-ground state when the
player isn't moving.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x17


@dataclass(frozen=True, slots=True)
class Flying:
    on_ground: bool


def decode(reader: Reader) -> Flying:
    b = reader.read(1)[0]
    if b not in (0, 1):
        raise ValueOutOfRange("flying.on_ground", b)
    return Flying(on_ground=b == 1)


def encode(packet: Flying, writer: Writer) -> None:
    writer.write(b"\x01" if packet.on_ground else b"\x00")
