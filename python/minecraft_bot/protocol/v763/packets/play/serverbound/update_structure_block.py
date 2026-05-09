"""Packet `update_structure_block` (play/serverbound, id 0x2D). Op-only."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, position, string, varint

PACKET_ID = 0x2D


@dataclass(frozen=True, slots=True)
class UpdateStructureBlock:
    location: tuple[int, int, int]
    action: int          # varint
    mode: int            # varint
    name: str
    offset_x: int        # i8
    offset_y: int
    offset_z: int
    size_x: int          # i8
    size_y: int
    size_z: int
    mirror: int          # varint
    rotation: int        # varint
    metadata: str
    integrity: float     # f32
    seed: int            # varlong
    flags: int           # i8


def decode(reader: Reader) -> UpdateStructureBlock:
    loc = position.read(reader)
    act = varint.read(reader)
    mode = varint.read(reader)
    name = string.read(reader)
    ox, oy, oz = struct.unpack(">bbb", reader.read(3))
    sx, sy, sz = struct.unpack(">bbb", reader.read(3))
    mir = varint.read(reader)
    rot = varint.read(reader)
    meta = string.read(reader)
    integ, = struct.unpack(">f", reader.read(4))
    from minecraft_bot.codec import varlong
    seed = varlong.read(reader)
    flags, = struct.unpack(">b", reader.read(1))
    return UpdateStructureBlock(
        location=loc, action=act, mode=mode, name=name,
        offset_x=ox, offset_y=oy, offset_z=oz,
        size_x=sx, size_y=sy, size_z=sz,
        mirror=mir, rotation=rot, metadata=meta,
        integrity=integ, seed=seed, flags=flags,
    )


def encode(packet: UpdateStructureBlock, writer: Writer) -> None:
    position.write(packet.location, writer)
    varint.write(packet.action, writer)
    varint.write(packet.mode, writer)
    string.write(packet.name, writer)
    writer.write(struct.pack(">bbb", packet.offset_x, packet.offset_y, packet.offset_z))
    writer.write(struct.pack(">bbb", packet.size_x, packet.size_y, packet.size_z))
    varint.write(packet.mirror, writer)
    varint.write(packet.rotation, writer)
    string.write(packet.metadata, writer)
    writer.write(struct.pack(">f", packet.integrity))
    from minecraft_bot.codec import varlong
    varlong.write(packet.seed, writer)
    writer.write(struct.pack(">b", packet.flags))
