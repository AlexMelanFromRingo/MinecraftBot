"""Packet `set_cooldown` (play/clientbound, id 0x15).

Triggers a per-item cooldown overlay (ender pearl, chorus fruit, etc.).
``cooldown_ticks == 0`` clears the cooldown.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x15


@dataclass(frozen=True, slots=True)
class SetCooldown:
    item_id: int          # varint, item registry id
    cooldown_ticks: int   # varint


def decode(reader: Reader) -> SetCooldown:
    iid = varint.read(reader)
    ticks = varint.read(reader)
    return SetCooldown(item_id=iid, cooldown_ticks=ticks)


def encode(packet: SetCooldown, writer: Writer) -> None:
    varint.write(packet.item_id, writer)
    varint.write(packet.cooldown_ticks, writer)
