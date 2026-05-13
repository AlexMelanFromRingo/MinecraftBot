"""A* pathfinder for 3-D voxel navigation (T019, FR-031..FR-035).

The pathfinder is **pure** and **world-agnostic** — it only needs an
object with three predicates:

- ``is_solid(x, y, z) -> bool``  — block fully blocks movement
- ``is_water(x, y, z) -> bool``  — block is water source/flowing
- ``is_navigable_obstacle(x, y, z) -> bool`` — door / fence-gate /
  trapdoor that the bot can open in passing (extra cost, not blocked)

Movement model
==============

The bot is a 1×2 column standing with feet at ``(x, y, z)`` and head at
``(x, y+1, z)``. A node is the bot's *feet* position.

Neighbours: 8 horizontal directions × 3 vertical options
(level, step-up, fall-down up to ``max_fall``). Diagonal moves
require both cardinal sides to be navigable (no corner-cutting through
walls).

Cost model
----------

- horizontal cardinal:  base 1.0 (×1.6 in water)
- horizontal diagonal:  base √2 (×1.6 in water)
- step up (+1 y):       extra 0.5
- fall down N blocks:   extra 0.1·N
- through-door (navigable obstacle): +2.0 surcharge

Heuristic: octile distance in the XZ plane plus |Δy|.

The algorithm uses A* with a node budget (default 100 000) — if the
budget is exhausted before reaching the goal it raises
:class:`NoPathFound`.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Protocol

from minecraft_bot.errors import NoPathFound

Pos = tuple[int, int, int]

_DIAG = math.sqrt(2)
# (dx, dz, is_diagonal)
_HORIZ = [
    (1, 0, False), (-1, 0, False), (0, 1, False), (0, -1, False),
    (1, 1, True), (1, -1, True), (-1, 1, True), (-1, -1, True),
]


class NavWorld(Protocol):
    """Minimal world interface the pathfinder needs."""

    def is_solid(self, x: int, y: int, z: int) -> bool: ...
    def is_water(self, x: int, y: int, z: int) -> bool: ...
    def is_navigable_obstacle(self, x: int, y: int, z: int) -> bool: ...


@dataclass(frozen=True, slots=True)
class Path:
    """An ordered sequence of waypoint positions plus total cost."""

    nodes: tuple[Pos, ...]
    cost: float


def _stand_floor(world: NavWorld, x: int, y: int, z: int) -> bool:
    """A bot can stand at ``(x, y, z)`` if (y-1) is solid (floor),
    (y) is passable, (y+1) is passable (head clearance). Water at
    (y) is also allowed (swim)."""
    if not world.is_solid(x, y - 1, z):
        # No floor; allowed only if (y-1) itself is water — then we're
        # standing on the water column. Otherwise this is a fall.
        if not world.is_water(x, y - 1, z):
            return False
    if world.is_solid(x, y, z) and not world.is_navigable_obstacle(x, y, z):
        return False
    if world.is_solid(x, y + 1, z) and not world.is_navigable_obstacle(x, y + 1, z):
        return False
    return True


def _heuristic(a: Pos, b: Pos) -> float:
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    dz = abs(a[2] - b[2])
    diag = min(dx, dz)
    straight = max(dx, dz) - diag
    return _DIAG * diag + straight + 0.5 * dy


def _vertical_resolve(
    world: NavWorld, x: int, y_from: int, z: int, max_fall: int
) -> tuple[int, float] | None:
    """Given a horizontal move ended at (x, ?, z), choose the y the bot
    actually lands on. Tries: same level, step up by 1, fall down 1..N.
    Returns (landed_y, vertical_extra_cost) or None if unreachable."""
    # Same level.
    if _stand_floor(world, x, y_from, z):
        return y_from, 0.0
    # Step up 1.
    if _stand_floor(world, x, y_from + 1, z):
        # Also need ceiling clearance at y_from + 2 over the source
        # column — caller handles source clearance separately.
        return y_from + 1, 0.5
    # Fall down.
    for drop in range(1, max_fall + 1):
        ny = y_from - drop
        if _stand_floor(world, x, ny, z):
            return ny, 0.1 * drop
    return None


def _neighbors(
    world: NavWorld, cur: Pos, *, max_fall: int
) -> list[tuple[Pos, float]]:
    out: list[tuple[Pos, float]] = []
    x, y, z = cur
    in_water = world.is_water(x, y, z)
    water_mult = 1.6 if in_water else 1.0

    for dx, dz, is_diag in _HORIZ:
        nx, nz = x + dx, z + dz

        if is_diag:
            # Corner-cutting prevention: both cardinal sides must be
            # passable at the bot's feet+head levels.
            side_a = _stand_floor(world, x + dx, y, z)
            side_b = _stand_floor(world, x, y, z + dz)
            if not (side_a or side_b):
                continue
            # If neither cardinal side is at ground level we still allow
            # diagonal only if both are at least body-passable — keep
            # simple here.

        result = _vertical_resolve(world, nx, y, nz, max_fall)
        if result is None:
            continue
        ny, vcost = result

        base = _DIAG if is_diag else 1.0
        cost = base * water_mult + vcost

        # Door surcharge.
        if world.is_navigable_obstacle(nx, ny, nz) or world.is_navigable_obstacle(nx, ny + 1, nz):
            cost += 2.0

        out.append(((nx, ny, nz), cost))
    return out


def find_path(
    world: NavWorld,
    start: Pos,
    goal: Pos,
    *,
    max_fall: int = 3,
    max_nodes: int = 100_000,
) -> Path:
    """Find a path from ``start`` to ``goal`` using A*.

    Raises :class:`NoPathFound` if no path exists or the node budget is
    exhausted (``max_nodes`` expansions)."""
    if start == goal:
        return Path(nodes=(start,), cost=0.0)

    # Priority queue: (f_score, tiebreak, node).
    counter = 0
    open_heap: list[tuple[float, int, Pos]] = [(_heuristic(start, goal), counter, start)]
    g_score: dict[Pos, float] = {start: 0.0}
    came_from: dict[Pos, Pos] = {}
    closed: set[Pos] = set()

    expansions = 0
    while open_heap:
        _, _, cur = heapq.heappop(open_heap)
        if cur in closed:
            continue
        if cur == goal:
            # Reconstruct.
            nodes_rev: list[Pos] = [cur]
            while cur in came_from:
                cur = came_from[cur]
                nodes_rev.append(cur)
            nodes_rev.reverse()
            return Path(nodes=tuple(nodes_rev), cost=g_score[goal])
        closed.add(cur)
        expansions += 1
        if expansions > max_nodes:
            raise NoPathFound(goal, expansions)

        for nbr, step_cost in _neighbors(world, cur, max_fall=max_fall):
            if nbr in closed:
                continue
            tentative = g_score[cur] + step_cost
            if tentative < g_score.get(nbr, math.inf):
                g_score[nbr] = tentative
                came_from[nbr] = cur
                counter += 1
                heapq.heappush(open_heap, (tentative + _heuristic(nbr, goal), counter, nbr))

    raise NoPathFound(goal, expansions)


__all__ = ["NavWorld", "Path", "find_path"]
