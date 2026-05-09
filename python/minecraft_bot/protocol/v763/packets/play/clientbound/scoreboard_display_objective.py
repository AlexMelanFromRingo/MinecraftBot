"""Packet `scoreboard_display_objective` (play/clientbound, id 0x51).

Selects which objective to display in a sidebar slot. ``position`` is
the slot id (0=list, 1=sidebar, 2=below-name, 3-18=team-coloured
sidebars).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string

PACKET_ID = 0x51


@dataclass(frozen=True, slots=True)
class ScoreboardDisplayObjective:
    position: int  # i8, slot id
    name: str      # objective name (max 16)


def decode(reader: Reader) -> ScoreboardDisplayObjective:
    pos, = struct.unpack(">b", reader.read(1))
    nm = string.read(reader)
    return ScoreboardDisplayObjective(position=pos, name=nm)


def encode(packet: ScoreboardDisplayObjective, writer: Writer) -> None:
    writer.write(struct.pack(">b", packet.position))
    string.write(packet.name, writer)
