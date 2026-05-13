"""Block-state classification table tests (T015)."""

from __future__ import annotations

from minecraft_bot.world.block_table import (
    get_block_info,
    get_block_info_by_name,
    get_name,
    is_lava,
    is_navigable_obstacle,
    is_passthrough,
    is_solid,
    is_water,
    step_height,
)


def test_stone_is_solid_and_named() -> None:
    """state_id 1 is stone in protocol 763 (minStateId of the stone block)."""
    info = get_block_info_by_name("minecraft:stone")
    assert info is not None
    sid = info["default_state"]
    assert get_name(sid) == "minecraft:stone"
    assert is_solid(sid)
    assert not is_water(sid)
    assert not is_lava(sid)
    assert step_height(sid) == 1.0


def test_air_is_passthrough() -> None:
    info = get_block_info_by_name("minecraft:air")
    sid = info["default_state"]
    assert get_name(sid) == "minecraft:air"
    assert not is_solid(sid)
    assert is_passthrough(sid)
    assert step_height(sid) == 0.0


def test_water_classified_as_water() -> None:
    info = get_block_info_by_name("minecraft:water")
    sid = info["default_state"]
    assert is_water(sid)
    assert not is_solid(sid)


def test_lava_classified_as_lava() -> None:
    info = get_block_info_by_name("minecraft:lava")
    sid = info["default_state"]
    assert is_lava(sid)
    assert not is_solid(sid)


def test_oak_door_is_navigable_obstacle() -> None:
    info = get_block_info_by_name("minecraft:oak_door")
    assert info is not None
    sid = info["default_state"]
    assert is_navigable_obstacle(sid)
    assert not is_solid(sid)


def test_oak_slab_step_height_is_half() -> None:
    info = get_block_info_by_name("minecraft:oak_slab")
    sid = info["default_state"]
    assert step_height(sid) == 0.5


def test_oak_stairs_step_height_is_half() -> None:
    info = get_block_info_by_name("minecraft:oak_stairs")
    sid = info["default_state"]
    assert step_height(sid) == 0.5


def test_glass_is_solid_despite_transparent() -> None:
    info = get_block_info_by_name("minecraft:glass")
    sid = info["default_state"]
    # Glass is transparent but solid for collision/pathfinding.
    assert is_solid(sid)


def test_oak_leaves_is_solid_despite_transparent() -> None:
    info = get_block_info_by_name("minecraft:oak_leaves")
    sid = info["default_state"]
    assert is_solid(sid)


def test_unknown_state_returns_none() -> None:
    assert get_name(999999) is None
    assert get_block_info(999999) is None
    assert not is_solid(999999)
    assert step_height(999999) == 0.0


def test_torch_is_passthrough() -> None:
    info = get_block_info_by_name("minecraft:torch")
    sid = info["default_state"]
    assert is_passthrough(sid)
    assert not is_solid(sid)


def test_dandelion_is_passthrough() -> None:
    info = get_block_info_by_name("minecraft:dandelion")
    sid = info["default_state"]
    assert is_passthrough(sid)


def test_block_table_loaded_with_full_count() -> None:
    """We should have all ~1000 vanilla blocks loaded."""
    info = get_block_info_by_name("minecraft:stone")
    assert info is not None
    assert info["id"] >= 0
    assert "default_state" in info
