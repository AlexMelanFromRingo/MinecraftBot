"""Packet `explosion` (play/clientbound, id 0x1D).

Plays an explosion effect at a world position. ``affected_block_offsets``
is the list of relative block offsets that should be destroyed/animated;
``player_motion_*`` is the impulse the explosion applies to the player.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x1D


@dataclass(frozen=True, slots=True)
class Explosion:
    x: float
    y: float
    z: float
    radius: float                                    # f32
    affected_block_offsets: tuple[tuple[int, int, int], ...]  # i8 triples
    player_motion_x: float                           # f32
    player_motion_y: float                           # f32
    player_motion_z: float                           # f32


def decode(reader: Reader) -> Explosion:
    x, y, z = struct.unpack(">ddd", reader.read(24))
    radius, = struct.unpack(">f", reader.read(4))
    n = varint.read(reader)
    offsets: list[tuple[int, int, int]] = []
    for _ in range(n):
        ox, oy, oz = struct.unpack(">bbb", reader.read(3))
        offsets.append((ox, oy, oz))
    pmx, pmy, pmz = struct.unpack(">fff", reader.read(12))
    return Explosion(
        x=x, y=y, z=z, radius=radius,
        affected_block_offsets=tuple(offsets),
        player_motion_x=pmx, player_motion_y=pmy, player_motion_z=pmz,
    )


def encode(packet: Explosion, writer: Writer) -> None:
    writer.write(struct.pack(">ddd", packet.x, packet.y, packet.z))
    writer.write(struct.pack(">f", packet.radius))
    varint.write(len(packet.affected_block_offsets), writer)
    for ox, oy, oz in packet.affected_block_offsets:
        writer.write(struct.pack(">bbb", ox, oy, oz))
    writer.write(struct.pack(">fff", packet.player_motion_x,
                              packet.player_motion_y, packet.player_motion_z))
