"""Packet `respawn` (play/clientbound, id 0x41).

Sent after a player dies and reuses their existing connection in a
(possibly different) dimension.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, position, string, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x41


@dataclass(frozen=True, slots=True)
class DeathLocation:
    dimension_name: str
    location: tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class Respawn:
    dimension: str
    world_name: str
    hashed_seed: int            # i64
    gamemode: int               # i8
    previous_gamemode: int      # u8
    is_debug: bool
    is_flat: bool
    copy_metadata: bool
    death: DeathLocation | None
    portal_cooldown: int        # varint


def _read_bool(reader: Reader, field: str) -> bool:
    b = reader.read(1)[0]
    if b not in (0, 1):
        raise ValueOutOfRange(field, b)
    return b == 1


def decode(reader: Reader) -> Respawn:
    dim = string.read(reader)
    wn = string.read(reader)
    hs, = struct.unpack(">q", reader.read(8))
    gm, = struct.unpack(">b", reader.read(1))
    pgm = reader.read(1)[0]
    is_d = _read_bool(reader, "respawn.is_debug")
    is_f = _read_bool(reader, "respawn.is_flat")
    cm = _read_bool(reader, "respawn.copy_metadata")
    has_death = _read_bool(reader, "respawn.has_death")
    death = None
    if has_death:
        dn = string.read(reader)
        loc = position.read(reader)
        death = DeathLocation(dimension_name=dn, location=loc)
    pc = varint.read(reader)
    return Respawn(
        dimension=dim, world_name=wn, hashed_seed=hs,
        gamemode=gm, previous_gamemode=pgm,
        is_debug=is_d, is_flat=is_f, copy_metadata=cm,
        death=death, portal_cooldown=pc,
    )


def encode(packet: Respawn, writer: Writer) -> None:
    string.write(packet.dimension, writer)
    string.write(packet.world_name, writer)
    writer.write(struct.pack(">q", packet.hashed_seed))
    writer.write(struct.pack(">b", packet.gamemode))
    writer.write(bytes([packet.previous_gamemode & 0xFF]))
    for flag in (packet.is_debug, packet.is_flat, packet.copy_metadata):
        writer.write(b"\x01" if flag else b"\x00")
    if packet.death is None:
        writer.write(b"\x00")
    else:
        writer.write(b"\x01")
        string.write(packet.death.dimension_name, writer)
        position.write(packet.death.location, writer)
    varint.write(packet.portal_cooldown, writer)
