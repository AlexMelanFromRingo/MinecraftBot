"""Packet `world_border_lerp_size` (play/clientbound, id 0x48).

Smoothly interpolates the border diameter from ``old_diameter`` to
``new_diameter`` over ``speed`` ticks.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x48


@dataclass(frozen=True, slots=True)
class WorldBorderLerpSize:
    old_diameter: float
    new_diameter: float
    speed: int  # varint, ticks (often a Long in practice; minecraft-data says varint)


def decode(reader: Reader) -> WorldBorderLerpSize:
    old, new = struct.unpack(">dd", reader.read(16))
    speed = varint.read(reader)
    return WorldBorderLerpSize(old_diameter=old, new_diameter=new, speed=speed)


def encode(packet: WorldBorderLerpSize, writer: Writer) -> None:
    writer.write(struct.pack(">dd", packet.old_diameter, packet.new_diameter))
    varint.write(packet.speed, writer)
