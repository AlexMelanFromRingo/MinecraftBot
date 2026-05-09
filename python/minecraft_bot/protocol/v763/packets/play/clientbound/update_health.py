"""Packet `update_health` (play/clientbound, id 0x57)."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x57


@dataclass(frozen=True, slots=True)
class UpdateHealth:
    health: float            # f32; 0.0 = dead, 20.0 = full
    food: int                # varint, 0..20
    food_saturation: float   # f32; 0..5.0 typical


def decode(reader: Reader) -> UpdateHealth:
    h, = struct.unpack(">f", reader.read(4))
    f = varint.read(reader)
    s, = struct.unpack(">f", reader.read(4))
    return UpdateHealth(health=h, food=f, food_saturation=s)


def encode(packet: UpdateHealth, writer: Writer) -> None:
    writer.write(struct.pack(">f", packet.health))
    varint.write(packet.food, writer)
    writer.write(struct.pack(">f", packet.food_saturation))
