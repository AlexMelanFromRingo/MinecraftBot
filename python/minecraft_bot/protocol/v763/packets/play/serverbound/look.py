"""Packet `look` (play/serverbound, id 0x16). Rotation-only update."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x16


@dataclass(frozen=True, slots=True)
class Look:
    yaw: float
    pitch: float
    on_ground: bool


def decode(reader: Reader) -> Look:
    yaw, pitch = struct.unpack(">ff", reader.read(8))
    og = reader.read(1)[0]
    if og not in (0, 1):
        raise ValueOutOfRange("look.on_ground", og)
    return Look(yaw=yaw, pitch=pitch, on_ground=og == 1)


def encode(packet: Look, writer: Writer) -> None:
    writer.write(struct.pack(">ff", packet.yaw, packet.pitch))
    writer.write(b"\x01" if packet.on_ground else b"\x00")
