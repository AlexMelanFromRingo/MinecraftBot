"""Packet `animation` (play/clientbound, id 0x04).

``animation`` codes: 0=swing main hand, 1=hurt, 2=leave bed, 3=swing offhand,
4=critical effect, 5=magic critical effect.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x04


@dataclass(frozen=True, slots=True)
class Animation:
    entity_id: int   # varint
    animation: int   # u8


def decode(reader: Reader) -> Animation:
    eid = varint.read(reader)
    anim = reader.read(1)[0]
    return Animation(entity_id=eid, animation=anim)


def encode(packet: Animation, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    writer.write(bytes([packet.animation & 0xFF]))
