"""Packet `scoreboard_objective` (play/clientbound, id 0x58).

Manages scoreboard objectives. ``action`` codes: 0=create, 1=remove,
2=update display.

For action 0/2 the packet carries display_text (JSON chat component)
and type (varint: 0=integer, 1=hearts). For action 1, no extra fields.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional

from minecraft_bot.codec import Reader, Writer, string, varint

PACKET_ID = 0x58


@dataclass(frozen=True, slots=True)
class ScoreboardObjective:
    name: str                       # max 16
    action: int                     # i8: 0/1/2
    display_text: Optional[str]     # JSON chat, only when action != 1
    objective_type: Optional[int]   # varint, only when action != 1


def decode(reader: Reader) -> ScoreboardObjective:
    nm = string.read(reader)
    act, = struct.unpack(">b", reader.read(1))
    if act in (0, 2):
        dt: Optional[str] = string.read(reader)
        ot: Optional[int] = varint.read(reader)
    else:
        dt, ot = None, None
    return ScoreboardObjective(name=nm, action=act, display_text=dt, objective_type=ot)


def encode(packet: ScoreboardObjective, writer: Writer) -> None:
    string.write(packet.name, writer)
    writer.write(struct.pack(">b", packet.action))
    if packet.action in (0, 2):
        if packet.display_text is None or packet.objective_type is None:
            from minecraft_bot.errors import ValueOutOfRange
            raise ValueOutOfRange("scoreboard_objective.action_extras", packet.action)
        string.write(packet.display_text, writer)
        varint.write(packet.objective_type, writer)
