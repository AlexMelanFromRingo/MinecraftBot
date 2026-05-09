"""Packet `world_border_warning_reach` (play/clientbound, id 0x4B).

Distance (in blocks) at which the border-warning HUD overlay starts to
fade in.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x4B


@dataclass(frozen=True, slots=True)
class WorldBorderWarningReach:
    warning_blocks: int  # varint


def decode(reader: Reader) -> WorldBorderWarningReach:
    return WorldBorderWarningReach(warning_blocks=varint.read(reader))


def encode(packet: WorldBorderWarningReach, writer: Writer) -> None:
    varint.write(packet.warning_blocks, writer)
