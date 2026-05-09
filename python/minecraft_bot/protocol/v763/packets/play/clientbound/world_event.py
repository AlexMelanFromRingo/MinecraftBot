"""Packet `world_event` (play/clientbound, id 0x25).

Generic world-event notification (block break particles, dispenser
fire, smoke, etc.). ``effect_id`` codes are listed at
https://minecraft.wiki/w/Java_Edition_protocol#World_Event.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, position
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x25


@dataclass(frozen=True, slots=True)
class WorldEvent:
    effect_id: int                  # i32
    location: tuple[int, int, int]  # Position
    data: int                       # i32; meaning depends on effect_id
    global_event: bool              # if True, ignore distance attenuation


def decode(reader: Reader) -> WorldEvent:
    eff, = struct.unpack(">i", reader.read(4))
    loc = position.read(reader)
    data, = struct.unpack(">i", reader.read(4))
    glob = reader.read(1)[0]
    if glob not in (0, 1):
        raise ValueOutOfRange("world_event.global", glob)
    return WorldEvent(effect_id=eff, location=loc, data=data, global_event=glob == 1)


def encode(packet: WorldEvent, writer: Writer) -> None:
    writer.write(struct.pack(">i", packet.effect_id))
    position.write(packet.location, writer)
    writer.write(struct.pack(">i", packet.data))
    writer.write(b"\x01" if packet.global_event else b"\x00")
