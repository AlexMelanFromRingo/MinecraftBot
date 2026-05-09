"""Packet `use_entity` (play/serverbound, id 0x10).

Player attacks or uses an entity. ``mouse``: 0=interact, 1=attack,
2=interact-at. For ``mouse == 2`` the packet carries hit-position
fields.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional

from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x10


@dataclass(frozen=True, slots=True)
class UseEntity:
    target: int                          # varint, target entity id
    mouse: int                           # varint, 0/1/2
    x: Optional[float]                   # f32, only when mouse == 2
    y: Optional[float]
    z: Optional[float]
    hand: Optional[int]                  # varint, only when mouse == 0 or 2
    sneaking: bool


def _bool(reader: Reader, name: str) -> bool:
    b = reader.read(1)[0]
    if b not in (0, 1):
        raise ValueOutOfRange(name, b)
    return b == 1


def decode(reader: Reader) -> UseEntity:
    target = varint.read(reader)
    mouse = varint.read(reader)
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    hand: Optional[int] = None
    if mouse == 2:
        x, y, z = struct.unpack(">fff", reader.read(12))
    if mouse == 0 or mouse == 2:
        hand = varint.read(reader)
    sneaking = _bool(reader, "use_entity.sneaking")
    return UseEntity(target=target, mouse=mouse, x=x, y=y, z=z, hand=hand, sneaking=sneaking)


def encode(packet: UseEntity, writer: Writer) -> None:
    varint.write(packet.target, writer)
    varint.write(packet.mouse, writer)
    if packet.mouse == 2:
        if packet.x is None or packet.y is None or packet.z is None:
            raise ValueOutOfRange("use_entity.xyz", None)
        writer.write(struct.pack(">fff", packet.x, packet.y, packet.z))
    if packet.mouse in (0, 2):
        if packet.hand is None:
            raise ValueOutOfRange("use_entity.hand", None)
        varint.write(packet.hand, writer)
    writer.write(b"\x01" if packet.sneaking else b"\x00")
