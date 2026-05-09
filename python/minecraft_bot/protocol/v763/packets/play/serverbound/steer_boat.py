"""Packet `steer_boat` (play/serverbound, id 0x19)."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x19


@dataclass(frozen=True, slots=True)
class SteerBoat:
    left_paddle: bool
    right_paddle: bool


def _bool(reader: Reader, name: str) -> bool:
    b = reader.read(1)[0]
    if b not in (0, 1):
        raise ValueOutOfRange(name, b)
    return b == 1


def decode(reader: Reader) -> SteerBoat:
    return SteerBoat(
        left_paddle=_bool(reader, "steer_boat.left"),
        right_paddle=_bool(reader, "steer_boat.right"),
    )


def encode(packet: SteerBoat, writer: Writer) -> None:
    writer.write(b"\x01" if packet.left_paddle else b"\x00")
    writer.write(b"\x01" if packet.right_paddle else b"\x00")
