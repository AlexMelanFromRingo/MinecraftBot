"""Packet `lock_difficulty` (play/serverbound, id 0x13). Op-only."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x13


@dataclass(frozen=True, slots=True)
class LockDifficulty:
    locked: bool


def decode(reader: Reader) -> LockDifficulty:
    b = reader.read(1)[0]
    if b not in (0, 1):
        raise ValueOutOfRange("lock_difficulty.locked", b)
    return LockDifficulty(locked=b == 1)


def encode(packet: LockDifficulty, writer: Writer) -> None:
    writer.write(b"\x01" if packet.locked else b"\x00")
