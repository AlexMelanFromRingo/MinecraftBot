"""AI observation API tests: raycast, voxel grid, chunks_around, observation."""

from __future__ import annotations

import struct

import pytest

from minecraft_bot.bot import Bot
from minecraft_bot.codec import Writer, nbt, varint
from minecraft_bot.observation import (
    ChunkView, Observation, RayHit, raycast, scan_volume, voxel_grid,
    world_map_3d,
)
from minecraft_bot.physics import PhysicsState
from minecraft_bot.protocol.v763.packets.play.clientbound.block_change import (
    BlockChange,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.map_chunk import (
    MapChunk,
)


def _air_chunk_payload(*, sections: int = 24) -> bytes:
    w = Writer()
    nbt.write(nbt.NbtCompound(), w)
    sec_w = Writer()
    for _ in range(sections):
        sec_w.write(struct.pack(">h", 0))
        sec_w.write(b"\x00")
        varint.write(0, sec_w)
        varint.write(0, sec_w)
        sec_w.write(b"\x00")
        varint.write(1, sec_w)
        varint.write(0, sec_w)
    sec_bytes = sec_w.bytes()
    varint.write(len(sec_bytes), w)
    w.write(sec_bytes)
    varint.write(0, w)
    return w.bytes()


def _bot_with_air_arena() -> Bot:
    bot = Bot.offline("h", 25565, "t")
    bot._has_initial_position = True
    bot._physics = PhysicsState(x=8.0, y=64.0, z=8.0, on_ground=True)
    bot.world.apply_map_chunk(MapChunk(chunk_x=0, chunk_z=0, payload=_air_chunk_payload()))
    return bot


# --- raycast ----------------------------------------------------------


def test_raycast_returns_none_for_clear_air() -> None:
    bot = _bot_with_air_arena()
    hit = bot.raycast(max_distance=8.0)
    assert hit is None


def test_raycast_hits_first_solid_block_along_direction() -> None:
    bot = _bot_with_air_arena()
    # Bot's eye is at y=65.62 (feet y=64 + 1.62). Place stone at the eye
    # level so the horizontal ray actually hits it.
    bot.world.apply_block_change(BlockChange(location=(13, 65, 8), block_state_id=1))
    bot._yaw = 270.0   # +X (east)
    bot._pitch = 0.0
    hit = bot.raycast(max_distance=10.0)
    assert isinstance(hit, RayHit)
    assert hit.x == 13
    assert hit.name == "minecraft:stone"
    assert 0 < hit.distance <= 10.0


def test_raycast_respects_max_distance() -> None:
    bot = _bot_with_air_arena()
    bot.world.apply_block_change(BlockChange(location=(50, 64, 8), block_state_id=1))
    bot._yaw = 270.0
    bot._pitch = 0.0
    assert bot.raycast(max_distance=5.0) is None


# --- scan_volume ----------------------------------------------------


def test_scan_volume_excludes_air_by_default() -> None:
    bot = _bot_with_air_arena()
    bot.world.apply_block_change(BlockChange(location=(9, 64, 8), block_state_id=1))
    bot.world.apply_block_change(BlockChange(location=(8, 64, 9), block_state_id=1))
    blocks = bot.scan_volume(radius=3)
    assert len(blocks) == 2
    # Sorted ascending by distance — both should be ~1 block away.
    for x, y, z, sid in blocks:
        assert sid == 1


def test_scan_volume_with_include_air_returns_cube() -> None:
    bot = _bot_with_air_arena()
    blocks = bot.scan_volume(radius=2, include_air=True)
    assert len(blocks) == (2 * 2 + 1) ** 3   # 5³ = 125


# --- voxel_grid -----------------------------------------------------


def test_voxel_grid_shape_and_origin() -> None:
    bot = _bot_with_air_arena()
    grid, origin = bot.voxel_grid(radius=2)
    side = 5
    assert len(grid) == side
    assert len(grid[0]) == side
    assert len(grid[0][0]) == side
    assert origin == (6, 62, 6)   # bot at (8, 64, 8) - radius 2


def test_voxel_grid_reflects_set_block() -> None:
    bot = _bot_with_air_arena()
    bot.world.apply_block_change(BlockChange(location=(8, 64, 8), block_state_id=1))
    grid, origin = bot.voxel_grid(radius=1)
    # grid[y][z][x]; bot at (8,64,8), origin (7,63,7).
    # The block we set is at grid[1][1][1] (centre of 3x3x3).
    assert grid[1][1][1] == 1


# --- chunks_around --------------------------------------------------


def test_chunks_around_finds_loaded_chunks() -> None:
    bot = _bot_with_air_arena()
    # Load a neighbouring chunk too.
    bot.world.apply_map_chunk(MapChunk(chunk_x=1, chunk_z=0, payload=_air_chunk_payload()))
    views = bot.chunks_around(radius_chunks=2)
    assert len(views) >= 2
    coords = [(v.cx, v.cz) for v in views]
    assert (0, 0) in coords
    assert (1, 0) in coords
    # First view should be the bot's own chunk (distance 0).
    assert views[0].cx == 0
    assert views[0].cz == 0
    assert views[0].distance_chunks == 0


def test_chunks_around_empty_when_radius_zero() -> None:
    bot = _bot_with_air_arena()
    views = bot.chunks_around(radius_chunks=0)
    assert len(views) == 1   # just the bot's chunk
    assert views[0].cx == 0


# --- world_map_3d ---------------------------------------------------


def test_world_map_3d_shape() -> None:
    bot = _bot_with_air_arena()
    grid, origin = bot.world_map_3d(radius_xz=4, radius_y=2)
    assert len(grid) == 5         # y side
    assert len(grid[0]) == 9      # z side
    assert len(grid[0][0]) == 9   # x side


# --- Observation composite -------------------------------------------


def test_observation_packs_full_state() -> None:
    bot = _bot_with_air_arena()
    bot.world.apply_block_change(BlockChange(location=(13, 65, 8), block_state_id=1))
    bot._yaw = 270.0
    bot._pitch = 0.0
    obs = bot.observation(voxel_radius=2, look_distance=10.0)
    assert isinstance(obs, Observation)
    assert obs.x == 8.0
    assert obs.health == 20.0
    assert obs.look_hit is not None
    assert obs.look_hit.x == 13
    # Voxel grid: 5×5×5
    assert len(obs.voxel_grid) == 5


def test_observation_picklable() -> None:
    import pickle
    bot = _bot_with_air_arena()
    obs = bot.observation(voxel_radius=2)
    data = pickle.dumps(obs)
    restored = pickle.loads(data)
    assert restored == obs
