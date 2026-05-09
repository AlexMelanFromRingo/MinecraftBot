"""Packet `world_border_warning_delay` (play/clientbound, id 0x4A).

Warning time before the border-shrink fully clamps. Seconds (varint).
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x4A


@dataclass(frozen=True, slots=True)
class WorldBorderWarningDelay:
    warning_time: int  # varint, seconds


def decode(reader: Reader) -> WorldBorderWarningDelay:
    return WorldBorderWarningDelay(warning_time=varint.read(reader))


def encode(packet: WorldBorderWarningDelay, writer: Writer) -> None:
    varint.write(packet.warning_time, writer)
