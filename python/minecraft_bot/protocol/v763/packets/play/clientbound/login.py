"""Packet `login` (play/clientbound, id 0x28).

Login (Play) — sent by the server immediately after the connection
transitions to PLAY. Carries the player's entity ID, gamemode, world
list, dimension codec (NBT), spawn dimension, and a bunch of
session-level flags.

Receiving this packet establishes the world's identity for the
session; the framework's :class:`Connection` records the entity ID
and (optionally) caches the dimension codec for callers that want to
introspect it.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional

from minecraft_bot.codec import Reader, Writer, nbt, position, string, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x28


@dataclass(frozen=True, slots=True)
class DeathLocation:
    dimension_name: str
    location: tuple[int, int, int]  # (x, y, z) packed Position


@dataclass(frozen=True, slots=True)
class Login:
    entity_id: int
    is_hardcore: bool
    game_mode: int               # u8
    previous_game_mode: int      # i8
    world_names: tuple[str, ...]
    dimension_codec: Optional[nbt.NbtTag]
    world_type: str              # current dimension type identifier
    world_name: str              # current dimension/world identifier
    hashed_seed: int             # i64
    max_players: int
    view_distance: int
    simulation_distance: int
    reduced_debug_info: bool
    enable_respawn_screen: bool
    is_debug: bool
    is_flat: bool
    death: Optional[DeathLocation]
    portal_cooldown: int         # varint


def _read_bool(reader: Reader) -> bool:
    b = reader.read(1)[0]
    if b not in (0, 1):
        raise ValueOutOfRange("bool", b)
    return b == 1


def decode(reader: Reader) -> Login:  # noqa: PLR0915 — long but flat
    (entity_id,) = struct.unpack(">i", reader.read(4))
    is_hardcore = _read_bool(reader)
    (game_mode,) = struct.unpack(">B", reader.read(1))
    (previous_game_mode,) = struct.unpack(">b", reader.read(1))
    n_worlds = varint.read(reader)
    world_names = tuple(string.read(reader) for _ in range(n_worlds))
    dimension_codec = nbt.read(reader)
    world_type = string.read(reader)
    world_name = string.read(reader)
    (hashed_seed,) = struct.unpack(">q", reader.read(8))
    max_players = varint.read(reader)
    view_distance = varint.read(reader)
    simulation_distance = varint.read(reader)
    reduced_debug_info = _read_bool(reader)
    enable_respawn_screen = _read_bool(reader)
    is_debug = _read_bool(reader)
    is_flat = _read_bool(reader)
    has_death = _read_bool(reader)
    death = None
    if has_death:
        dimension_name = string.read(reader)
        location = position.read(reader)
        death = DeathLocation(dimension_name=dimension_name, location=location)
    portal_cooldown = varint.read(reader)
    return Login(
        entity_id=entity_id, is_hardcore=is_hardcore,
        game_mode=game_mode, previous_game_mode=previous_game_mode,
        world_names=world_names, dimension_codec=dimension_codec,
        world_type=world_type, world_name=world_name, hashed_seed=hashed_seed,
        max_players=max_players, view_distance=view_distance,
        simulation_distance=simulation_distance,
        reduced_debug_info=reduced_debug_info,
        enable_respawn_screen=enable_respawn_screen,
        is_debug=is_debug, is_flat=is_flat, death=death,
        portal_cooldown=portal_cooldown,
    )


def encode(packet: Login, writer: Writer) -> None:  # noqa: PLR0915
    writer.write(struct.pack(">i", packet.entity_id))
    writer.write(b"\x01" if packet.is_hardcore else b"\x00")
    writer.write(struct.pack(">B", packet.game_mode))
    writer.write(struct.pack(">b", packet.previous_game_mode))
    varint.write(len(packet.world_names), writer)
    for w in packet.world_names:
        string.write(w, writer)
    nbt.write(packet.dimension_codec, writer)
    string.write(packet.world_type, writer)
    string.write(packet.world_name, writer)
    writer.write(struct.pack(">q", packet.hashed_seed))
    varint.write(packet.max_players, writer)
    varint.write(packet.view_distance, writer)
    varint.write(packet.simulation_distance, writer)
    writer.write(b"\x01" if packet.reduced_debug_info else b"\x00")
    writer.write(b"\x01" if packet.enable_respawn_screen else b"\x00")
    writer.write(b"\x01" if packet.is_debug else b"\x00")
    writer.write(b"\x01" if packet.is_flat else b"\x00")
    if packet.death is None:
        writer.write(b"\x00")
    else:
        writer.write(b"\x01")
        string.write(packet.death.dimension_name, writer)
        position.write(packet.death.location, writer)
    varint.write(packet.portal_cooldown, writer)
