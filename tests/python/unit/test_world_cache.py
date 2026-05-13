"""World cache tests (T031)."""

from __future__ import annotations

import struct

from minecraft_bot.codec import Writer, nbt, varint
from minecraft_bot.protocol.v763.packets.play.clientbound.block_change import (
    BlockChange,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.map_chunk import (
    MapChunk,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.multi_block_change import (
    MultiBlockChange,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.unload_chunk import (
    UnloadChunk,
)
from minecraft_bot.world import block_table
from minecraft_bot.world.cache import World


def _make_air_chunk_payload(cx: int, cz: int, *, sections: int = 24) -> bytes:
    """Build a map_chunk payload where every block is air (state 0)."""
    w = Writer()
    nbt.write(nbt.NbtCompound(), w)
    sec_w = Writer()
    for _ in range(sections):
        sec_w.write(struct.pack(">h", 0))
        sec_w.write(b"\x00")           # block container bits=0
        varint.write(0, sec_w)         # single value=0 (air)
        varint.write(0, sec_w)         # n_longs=0
        sec_w.write(b"\x00")           # biome container bits=0
        varint.write(1, sec_w)         # plain biome
        varint.write(0, sec_w)
    sec_bytes = sec_w.bytes()
    varint.write(len(sec_bytes), w)
    w.write(sec_bytes)
    varint.write(0, w)                 # no block entities
    return w.bytes()


def _load_air_chunk(world: World, cx: int, cz: int) -> None:
    payload = _make_air_chunk_payload(cx, cz)
    world.apply_map_chunk(MapChunk(chunk_x=cx, chunk_z=cz, payload=payload))


def test_get_block_returns_air_for_unloaded_chunk() -> None:
    world = World()
    assert world.get_block(0, 64, 0) == 0
    assert world.get_block_name(0, 64, 0) in ("minecraft:air", None)


def test_load_chunk_then_query_air() -> None:
    world = World()
    _load_air_chunk(world, 0, 0)
    assert world.get_block(5, 64, 5) == 0
    assert (0, 0) in world.chunks


def test_block_change_updates_block_state() -> None:
    world = World()
    _load_air_chunk(world, 0, 0)
    stone = next(sid for sid, info in block_table._BLOCK_TABLE.items() if info["name"] == "minecraft:stone") if False else 1
    # Use state id 1 (stone) — known from block_states.json.
    world.apply_block_change(BlockChange(location=(3, 64, 7), block_state_id=1))
    assert world.get_block(3, 64, 7) == 1


def test_block_change_in_unloaded_chunk_silently_ignored() -> None:
    world = World()
    world.apply_block_change(BlockChange(location=(500, 64, 500), block_state_id=1))
    assert world.get_block(500, 64, 500) == 0  # still air


def test_multi_block_change_updates_section() -> None:
    world = World()
    _load_air_chunk(world, 0, 0)
    # Section (cx=0, cy=0 -> world y=0..15 wait, section_y=0 with min_y=-64
    # means absolute section y=0 = world y = -64..-49)
    # Build a record for (lx=2, ly=3, lz=4) -> world y = -64 + 3 = -61
    rel = (2 << 8) | (4 << 4) | 3
    rec = (1 << 12) | rel  # state_id=1 stone
    world.apply_multi_block_change(MultiBlockChange(
        chunk_section_x=0, chunk_section_z=0, chunk_section_y=-4,  # min_y/16
        records=(rec,),
    ))
    assert world.get_block(2, -61, 4) == 1


def test_unload_chunk_drops_chunk() -> None:
    world = World()
    _load_air_chunk(world, 0, 0)
    assert (0, 0) in world.chunks
    world.apply_unload_chunk(UnloadChunk(chunk_x=0, chunk_z=0))
    assert (0, 0) not in world.chunks
    assert world.get_block(0, 64, 0) == 0


def test_reset_clears_cache_and_optionally_updates_dimension() -> None:
    world = World()
    _load_air_chunk(world, 0, 0)
    _load_air_chunk(world, 1, 0)
    assert len(world) == 2
    world.reset(dimension="minecraft:the_nether", min_y=0, section_count=16)
    assert len(world) == 0
    assert world.dimension == "minecraft:the_nether"
    assert world.min_y == 0
    assert world.section_count == 16


def test_find_blocks_nearby_sorts_by_distance() -> None:
    world = World()
    _load_air_chunk(world, 0, 0)
    # Place stone blocks at known offsets
    stone_id = 1
    targets = [(3, 64, 0), (1, 64, 0), (5, 64, 5)]
    for x, y, z in targets:
        world.apply_block_change(BlockChange(location=(x, y, z), block_state_id=stone_id))

    results = world.find_blocks_nearby(
        "minecraft:stone", origin=(0.0, 64.0, 0.0), radius=16, limit=5,
    )
    assert len(results) == 3
    # Ascending by distance
    assert results[0] == (1, 64, 0)   # closest
    assert results[1] == (3, 64, 0)
    assert results[2] == (5, 64, 5)


def test_find_blocks_nearby_respects_limit() -> None:
    world = World()
    _load_air_chunk(world, 0, 0)
    stone_id = 1
    for x in range(0, 10):
        world.apply_block_change(BlockChange(location=(x, 64, 0), block_state_id=stone_id))
    out = world.find_blocks_nearby(
        "minecraft:stone", origin=(0.0, 64.0, 0.0), radius=20, limit=3,
    )
    assert len(out) == 3
