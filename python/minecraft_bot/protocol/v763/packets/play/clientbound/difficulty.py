"""Packet `difficulty` (play/clientbound, id 0x0C).

Server's announcement of the world's current difficulty: 0=peaceful,
1=easy, 2=normal, 3=hard. ``locked`` indicates the player can't change it.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x0C


@dataclass(frozen=True, slots=True)
class Difficulty:
    difficulty: int        # u8
    locked: bool


def decode(reader: Reader) -> Difficulty:
    diff = reader.read(1)[0]
    locked_byte = reader.read(1)[0]
    if locked_byte not in (0, 1):
        raise ValueOutOfRange("difficulty.locked", locked_byte)
    return Difficulty(difficulty=diff, locked=locked_byte == 1)


def encode(packet: Difficulty, writer: Writer) -> None:
    writer.write(bytes([packet.difficulty & 0xFF]))
    writer.write(b"\x01" if packet.locked else b"\x00")
