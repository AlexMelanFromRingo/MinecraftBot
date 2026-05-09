"""Packet `entity_action` (play/serverbound, id 0x1E).

``action_id``: 0=start sneak, 1=stop sneak, 2=leave bed, 3=start sprint,
4=stop sprint, 5=start jump-with-horse, 6=stop jump-with-horse,
7=open horse inv, 8=start flying with elytra, 9=start spin attack.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x1E


@dataclass(frozen=True, slots=True)
class EntityAction:
    entity_id: int
    action_id: int
    jump_boost: int  # varint, 0..100 for horse jump


def decode(reader: Reader) -> EntityAction:
    return EntityAction(
        entity_id=varint.read(reader),
        action_id=varint.read(reader),
        jump_boost=varint.read(reader),
    )


def encode(packet: EntityAction, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    varint.write(packet.action_id, writer)
    varint.write(packet.jump_boost, writer)
