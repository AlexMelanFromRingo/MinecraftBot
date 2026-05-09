"""Packet `death_combat_event` (play/clientbound, id 0x38).

Server announces the player's death. ``message`` is a JSON chat
component describing the cause (e.g., "You were slain by Zombie").
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint

PACKET_ID = 0x38


@dataclass(frozen=True, slots=True)
class DeathCombatEvent:
    player_id: int  # varint, the player's entity id
    message: str    # JSON chat component


def decode(reader: Reader) -> DeathCombatEvent:
    pid = varint.read(reader)
    msg = string.read(reader)
    return DeathCombatEvent(player_id=pid, message=msg)


def encode(packet: DeathCombatEvent, writer: Writer) -> None:
    varint.write(packet.player_id, writer)
    string.write(packet.message, writer)
