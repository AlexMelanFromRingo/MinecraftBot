"""Packet `arm_animation` (play/serverbound, id 0x2F).

Player swung an arm. ``hand``: 0=main, 1=off.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x2F


@dataclass(frozen=True, slots=True)
class ArmAnimation:
    hand: int  # varint


def decode(reader: Reader) -> ArmAnimation:
    return ArmAnimation(hand=varint.read(reader))


def encode(packet: ArmAnimation, writer: Writer) -> None:
    varint.write(packet.hand, writer)
