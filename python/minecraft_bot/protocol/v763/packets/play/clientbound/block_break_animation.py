"""Packet `block_break_animation` (play/clientbound, id 0x07).

``destroy_stage`` is 0..9 (visible stages); 10+ resets the animation.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, position, varint

PACKET_ID = 0x07


@dataclass(frozen=True, slots=True)
class BlockBreakAnimation:
    entity_id: int                    # varint
    location: tuple[int, int, int]    # Position
    destroy_stage: int                # i8


def decode(reader: Reader) -> BlockBreakAnimation:
    eid = varint.read(reader)
    loc = position.read(reader)
    (stage,) = struct.unpack(">b", reader.read(1))
    return BlockBreakAnimation(entity_id=eid, location=loc, destroy_stage=stage)


def encode(packet: BlockBreakAnimation, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    position.write(packet.location, writer)
    writer.write(struct.pack(">b", packet.destroy_stage))
