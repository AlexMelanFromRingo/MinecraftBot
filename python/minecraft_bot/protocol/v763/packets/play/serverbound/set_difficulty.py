"""Packet `set_difficulty` (play/serverbound, id 0x02). Op-only."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x02


@dataclass(frozen=True, slots=True)
class SetDifficulty:
    new_difficulty: int  # u8


def decode(reader: Reader) -> SetDifficulty:
    return SetDifficulty(new_difficulty=reader.read(1)[0])


def encode(packet: SetDifficulty, writer: Writer) -> None:
    writer.write(bytes([packet.new_difficulty & 0xFF]))
