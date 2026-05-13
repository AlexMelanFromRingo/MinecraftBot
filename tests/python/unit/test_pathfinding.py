"""A* pathfinder tests (T020).

Tests use a tiny ASCII-grid synthetic World — each character at
column ``x``, row ``z`` represents a column of blocks::

    .   air at floor level (y=64), solid at y=63, air above
    #   solid wall (blocks pass-through, fills y=64..65)
    ~   water at y=64
    D   navigable obstacle (door) at y=64
    S   start position (treated as air at y=64)
    T   target position (treated as air at y=64)
"""

from __future__ import annotations

import pytest
from minecraft_bot.errors import NoPathFound
from minecraft_bot.pathfinding import Path, find_path


class GridWorld:
    """Minimal World-like for tests. y=63 is solid floor everywhere;
    y=64 is the bot's feet level; y=65 is head level."""

    def __init__(self, ascii_grid: list[str]) -> None:
        self.rows = ascii_grid

    def cell(self, x: int, z: int) -> str:
        if z < 0 or z >= len(self.rows) or x < 0 or x >= len(self.rows[z]):
            return "#"  # out of bounds = solid wall
        return self.rows[z][x]

    def is_solid(self, x: int, y: int, z: int) -> bool:
        if y < 63:
            return True  # bedrock-ish floor
        c = self.cell(x, z)
        if y == 63:
            return c != "P"  # floor solid unless cell is pit
        if y in (64, 65):
            return c == "#"
        return False

    def is_water(self, x: int, y: int, z: int) -> bool:
        return self.cell(x, z) == "~" and y == 64

    def is_navigable_obstacle(self, x: int, y: int, z: int) -> bool:
        return self.cell(x, z) == "D" and y == 64

    def find_marker(self, marker: str) -> tuple[int, int, int]:
        for z, row in enumerate(self.rows):
            for x, c in enumerate(row):
                if c == marker:
                    return (x, 64, z)
        raise ValueError(f"marker {marker} not in grid")


# --- straight-line flat path ----------------------------------------------


def test_flat_straight_path() -> None:
    world = GridWorld(["S....T"])
    start = world.find_marker("S")
    goal = world.find_marker("T")
    path = find_path(world, start, goal)
    assert isinstance(path, Path)
    assert path.nodes[0] == start
    assert path.nodes[-1] == goal
    assert len(path.nodes) == 6  # 5 cardinal hops


# --- diagonal path ----------------------------------------------------


def test_diagonal_path() -> None:
    world = GridWorld([
        "S....",
        ".....",
        ".....",
        ".....",
        "....T",
    ])
    start = world.find_marker("S")
    goal = world.find_marker("T")
    path = find_path(world, start, goal)
    # Diagonal-optimal: 4 diagonal steps.
    assert len(path.nodes) == 5


# --- obstacle avoidance -----------------------------------------------


def test_walls_route_around() -> None:
    world = GridWorld([
        "S....",
        "####.",
        ".....",
        ".####",
        "....T",
    ])
    start = world.find_marker("S")
    goal = world.find_marker("T")
    path = find_path(world, start, goal)
    assert path.nodes[0] == start
    assert path.nodes[-1] == goal


# --- door (navigable obstacle) -----------------------------------------


def test_door_traversal_adds_cost() -> None:
    world_clear = GridWorld(["S...T"])
    world_door = GridWorld(["S.D.T"])
    p_clear = find_path(world_clear, world_clear.find_marker("S"), world_clear.find_marker("T"))
    p_door = find_path(world_door, world_door.find_marker("S"), world_door.find_marker("T"))
    assert p_door.cost > p_clear.cost


# --- water path costs more --------------------------------------------


def test_water_path_costs_more_than_land() -> None:
    world_land = GridWorld(["S...T"])
    world_water = GridWorld(["S~~~T"])
    p_land = find_path(world_land, world_land.find_marker("S"), world_land.find_marker("T"))
    p_water = find_path(world_water, world_water.find_marker("S"), world_water.find_marker("T"))
    assert p_water.cost > p_land.cost


# --- walled-off target -------------------------------------------------


def test_walled_off_target_raises() -> None:
    world_blocked = GridWorld([
        "S#T",
        "###",
        "###",
    ])
    with pytest.raises(NoPathFound):
        find_path(
            world_blocked,
            world_blocked.find_marker("S"),
            world_blocked.find_marker("T"),
        )


# --- node budget exceeded ----------------------------------------------


def test_node_budget_exceeded_raises() -> None:
    world = GridWorld(["S" + "." * 100 + "T"])
    with pytest.raises(NoPathFound):
        find_path(world, world.find_marker("S"), world.find_marker("T"), max_nodes=10)


# --- start == goal ----------------------------------------------------


def test_start_equals_goal() -> None:
    world = GridWorld(["S"])
    start = world.find_marker("S")
    path = find_path(world, start, start)
    assert path.nodes == (start,)
    assert path.cost == 0.0
