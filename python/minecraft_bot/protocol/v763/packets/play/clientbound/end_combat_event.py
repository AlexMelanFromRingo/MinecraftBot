"""Packet `end_combat_event` (play/clientbound, id 0x36).

Server signals the end of a combat sequence. ``duration`` is in ticks.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x36


@dataclass(frozen=True, slots=True)
class EndCombatEvent:
    duration: int  # varint, ticks


def decode(reader: Reader) -> EndCombatEvent:
    return EndCombatEvent(duration=varint.read(reader))


def encode(packet: EndCombatEvent, writer: Writer) -> None:
    varint.write(packet.duration, writer)
