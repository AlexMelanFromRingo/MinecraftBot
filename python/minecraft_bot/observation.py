"""AI-agent observation API: raycast + voxel grid + snapshots.

These helpers expose the world "as the bot sees it" so RL/ML agents can
build observation tensors without poking at low-level cache details.

- :func:`raycast`        — first solid hit along the bot's eye-ray
- :func:`scan_volume`    — every block in a sphere around a point
- :func:`voxel_grid`     — a fixed-shape (N×M×N) numpy-friendly grid
                           of block-state IDs, suitable for CNNs
- :class:`Observation`   — composite snapshot for one agent step
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from minecraft_bot.world import block_table

if TYPE_CHECKING:
    from minecraft_bot.world.cache import World


@dataclass(frozen=True, slots=True)
class RayHit:
    """A successful raycast hit."""

    x: int
    y: int
    z: int
    state_id: int
    name: str
    face: int        # 0=bottom .. 5=east (Minecraft face conventions)
    distance: float  # eye → hit point in blocks


def _face_id(nx: float, ny: float, nz: float) -> int:
    """Pick the face whose outward normal has the strongest opposite
    component to the ray. Conventions: 0=bottom (-Y), 1=top (+Y),
    2=north (-Z), 3=south (+Z), 4=west (-X), 5=east (+X)."""
    ax, ay, az = abs(nx), abs(ny), abs(nz)
    if ax >= ay and ax >= az:
        return 5 if nx < 0 else 4
    if ay >= ax and ay >= az:
        return 1 if ny < 0 else 0
    return 3 if nz < 0 else 2


def raycast(
    world: "World",
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    *,
    max_distance: float = 32.0,
    step: float = 0.1,
) -> Optional[RayHit]:
    """Cast a ray from ``origin`` along (normalised) ``direction`` and
    return the first solid block it hits, or None if max_distance is
    exhausted.

    The march is uniform-step for simplicity — vs Amanatides-Woo grid
    traversal — which is plenty fast for the bot's reach (~5 blocks)
    and AI observation distances. The step (default 0.1) gives ~10
    samples per block; tighten if you need pixel-accurate face hits.
    """
    ox, oy, oz = origin
    dx, dy, dz = direction
    n = math.sqrt(dx * dx + dy * dy + dz * dz)
    if n == 0:
        return None
    dx, dy, dz = dx / n, dy / n, dz / n
    # Snap near-zero components so cardinal/diagonal rays don't drift
    # one cell off due to float-rounding in trig (cos(π/2) ≠ 0 exactly).
    _EPS = 1e-9
    if abs(dx) < _EPS:
        dx = 0.0
    if abs(dy) < _EPS:
        dy = 0.0
    if abs(dz) < _EPS:
        dz = 0.0
    t = 0.0
    last_block: Optional[tuple[int, int, int]] = None
    while t <= max_distance:
        px, py, pz = ox + dx * t, oy + dy * t, oz + dz * t
        bx, by, bz = math.floor(px), math.floor(py), math.floor(pz)
        if (bx, by, bz) != last_block:
            sid = world.get_block(bx, by, bz)
            if block_table.is_solid(sid):
                # Approximate the face by the dominant entry component.
                lbx, lby, lbz = last_block if last_block is not None else (bx, by, bz)
                face = _face_id(bx - lbx, by - lby, bz - lbz) if last_block else _face_id(dx, dy, dz)
                return RayHit(
                    x=bx, y=by, z=bz,
                    state_id=sid,
                    name=block_table.get_name(sid) or f"id_{sid}",
                    face=face,
                    distance=t,
                )
            last_block = (bx, by, bz)
        t += step
    return None


def scan_volume(
    world: "World",
    centre: tuple[float, float, float],
    *,
    radius: int = 8,
    include_air: bool = False,
) -> list[tuple[int, int, int, int]]:
    """Iterate every block within Chebyshev radius ``radius`` of
    ``centre`` (a cube of side ``2*radius+1``). Returns a list of
    ``(x, y, z, state_id)`` tuples sorted ascending by Euclidean
    distance from centre.

    If ``include_air`` is False (default), air blocks (state 0) are
    omitted. Useful for "what's in front of me" agent observations.
    """
    cx, cy, cz = centre
    icx, icy, icz = int(cx), int(cy), int(cz)
    out: list[tuple[float, int, int, int, int]] = []
    for dy in range(-radius, radius + 1):
        for dz in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                x, y, z = icx + dx, icy + dy, icz + dz
                sid = world.get_block(x, y, z)
                if not include_air and sid == 0:
                    continue
                ddx, ddy, ddz = x - cx, y - cy, z - cz
                d2 = ddx * ddx + ddy * ddy + ddz * ddz
                out.append((d2, x, y, z, sid))
    out.sort(key=lambda t: t[0])
    return [(x, y, z, sid) for _, x, y, z, sid in out]


def voxel_grid(
    world: "World",
    centre: tuple[float, float, float],
    *,
    radius: int = 8,
) -> tuple[list[list[list[int]]], tuple[int, int, int]]:
    """Build a 3-D (2r+1)³ grid of block-state IDs centred on ``centre``.

    Returns ``(grid, origin)`` where ``grid[y][z][x]`` is the state ID
    and ``origin`` is the world coordinate of ``grid[0][0][0]``. ML
    callers typically convert to ``numpy.array(grid)`` once they
    have numpy available — this module stays zero-dep.
    """
    cx, cy, cz = centre
    icx, icy, icz = int(cx), int(cy), int(cz)
    side = 2 * radius + 1
    origin = (icx - radius, icy - radius, icz - radius)
    grid: list[list[list[int]]] = [
        [
            [
                world.get_block(origin[0] + dx, origin[1] + dy, origin[2] + dz)
                for dx in range(side)
            ]
            for dz in range(side)
        ]
        for dy in range(side)
    ]
    return grid, origin


@dataclass(frozen=True, slots=True)
class ChunkView:
    """A reference to one loaded chunk near the bot.

    Lightweight wrapper that exposes a chunk's coordinates plus a
    reference back to the underlying :class:`Chunk` so callers can
    iterate without dropping into world.chunks themselves.
    """

    cx: int
    cz: int
    distance_chunks: int   # Chebyshev distance from the bot's own chunk
    chunk: object          # the actual Chunk instance (kept dynamic to avoid cyclic import)


def chunks_around(
    world: "World",
    centre: tuple[float, float, float],
    *,
    radius_chunks: int = 2,
) -> list[ChunkView]:
    """Return every loaded chunk whose Chebyshev distance to the bot's
    chunk is ≤ ``radius_chunks``.

    For ``radius_chunks=2`` you get up to a 5×5 = 25-chunk window;
    each chunk is 16×N×16, so for an overworld dimension that's a
    ~80×384×80-block region of source-of-truth voxel data.
    """
    cx0, cz0 = int(centre[0]) >> 4, int(centre[2]) >> 4
    out: list[ChunkView] = []
    for dcz in range(-radius_chunks, radius_chunks + 1):
        for dcx in range(-radius_chunks, radius_chunks + 1):
            cx, cz = cx0 + dcx, cz0 + dcz
            chunk = world.chunks.get((cx, cz))
            if chunk is None:
                continue
            out.append(ChunkView(
                cx=cx, cz=cz,
                distance_chunks=max(abs(dcx), abs(dcz)),
                chunk=chunk,
            ))
    out.sort(key=lambda v: v.distance_chunks)
    return out


def world_map_3d(
    world: "World",
    centre: tuple[float, float, float],
    *,
    radius_xz: int = 16,
    radius_y: Optional[int] = None,
) -> tuple[list[list[list[int]]], tuple[int, int, int]]:
    """Wider variant of :func:`voxel_grid`: rectangular box of block-state
    IDs (``[y][z][x]``) centred on the bot.

    ``radius_xz`` is the horizontal Chebyshev radius (box side =
    ``2*radius_xz + 1``). ``radius_y`` defaults to ``radius_xz`` but
    can be smaller (cheaper observation) or larger (skybox view).

    For RL/CNN consumption, do ``numpy.array(grid)`` once.
    """
    if radius_y is None:
        radius_y = radius_xz
    cx, cy, cz = centre
    icx, icy, icz = int(cx), int(cy), int(cz)
    origin = (icx - radius_xz, icy - radius_y, icz - radius_xz)
    side_xz = 2 * radius_xz + 1
    side_y = 2 * radius_y + 1
    grid: list[list[list[int]]] = [
        [
            [
                world.get_block(origin[0] + dx, origin[1] + dy, origin[2] + dz)
                for dx in range(side_xz)
            ]
            for dz in range(side_xz)
        ]
        for dy in range(side_y)
    ]
    return grid, origin


@dataclass(frozen=True, slots=True)
class Observation:
    """One AI-agent observation: bot state + visible world + entities.

    Composite of (a) what the bot is, (b) what it's looking at (ray
    hit), (c) what's around it (voxel grid), and (d) which entities
    are nearby. Picklable. Intended to be fed straight to an RL
    policy or a frozen evaluator.
    """

    # From BotSnapshot
    x: float
    y: float
    z: float
    yaw: float
    pitch: float
    on_ground: bool
    health: float
    food: int
    saturation: float
    held_slot: int

    # Look target
    look_hit: Optional[RayHit]

    # Voxel grid around the bot (state IDs)
    voxel_radius: int
    voxel_grid: tuple[tuple[tuple[int, ...], ...], ...]
    voxel_origin: tuple[int, int, int]

    # Closest N entities + closest N players + their types
    nearby_entities: tuple[tuple[str, float, float, float, float], ...] = field(default_factory=tuple)
    # (type_name, x, y, z, health_or_0)

    # Active effects
    active_effects: tuple[tuple[str, int, int], ...] = field(default_factory=tuple)
    # (name, amplifier, duration_ticks)


def _eye_direction(yaw_deg: float, pitch_deg: float) -> tuple[float, float, float]:
    """Convert Minecraft yaw/pitch (degrees) to an eye-vector."""
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    cy = math.cos(yaw)
    sy = math.sin(yaw)
    cp = math.cos(pitch)
    sp = math.sin(pitch)
    return (-sy * cp, -sp, cy * cp)


def make_observation(
    bot,
    *,
    voxel_radius: int = 4,
    nearby_radius: float = 16.0,
    look_distance: float = 32.0,
) -> Observation:
    """Construct an :class:`Observation` from the bot's current state."""
    eye_origin = (bot.x, bot.y + 1.62, bot.z)
    direction = _eye_direction(bot.yaw, bot.pitch)
    hit = raycast(bot.world, eye_origin, direction, max_distance=look_distance)

    grid, origin = voxel_grid(
        bot.world,
        (int(bot.x), int(bot.y), int(bot.z)),
        radius=voxel_radius,
    )
    # Convert nested lists to tuples for hashability/freezing.
    grid_t: tuple[tuple[tuple[int, ...], ...], ...] = tuple(
        tuple(tuple(row) for row in plane) for plane in grid
    )

    nearby = []
    for e in bot.nearby_entities(radius=nearby_radius):
        health = float(getattr(e, "health", 0.0) or 0.0)
        nearby.append((type(e).__name__, e.x, e.y, e.z, health))

    effects = tuple(
        (entry.name, entry.amplifier, entry.duration_ticks)
        for entry in bot.effects.active_effects()
    )

    return Observation(
        x=bot.x, y=bot.y, z=bot.z,
        yaw=bot.yaw, pitch=bot.pitch,
        on_ground=bot.on_ground,
        health=bot.health, food=bot.food, saturation=bot.saturation,
        held_slot=bot.held_slot,
        look_hit=hit,
        voxel_radius=voxel_radius,
        voxel_grid=grid_t,
        voxel_origin=origin,
        nearby_entities=tuple(nearby),
        active_effects=effects,
    )


__all__ = [
    "RayHit", "ChunkView", "Observation",
    "raycast", "scan_volume", "voxel_grid", "world_map_3d",
    "chunks_around", "make_observation",
]
