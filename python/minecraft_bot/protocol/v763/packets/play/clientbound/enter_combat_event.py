"""Packet `enter_combat_event` (play/clientbound, id 0x37).

No-payload signal that the player just entered combat (e.g., took damage
from another entity).
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x37


@dataclass(frozen=True, slots=True)
class EnterCombatEvent:
    """Empty packet."""


def decode(reader: Reader) -> EnterCombatEvent:
    return EnterCombatEvent()


def encode(packet: EnterCombatEvent, writer: Writer) -> None:
    pass
