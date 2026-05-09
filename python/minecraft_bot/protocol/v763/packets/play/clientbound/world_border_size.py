"""Packet `world_border_size` (play/clientbound, id 0x49)."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x49


@dataclass(frozen=True, slots=True)
class WorldBorderSize:
    diameter: float


def decode(reader: Reader) -> WorldBorderSize:
    d, = struct.unpack(">d", reader.read(8))
    return WorldBorderSize(diameter=d)


def encode(packet: WorldBorderSize, writer: Writer) -> None:
    writer.write(struct.pack(">d", packet.diameter))
