"""Per-tick physics (T021).

A **pure** physics step:

    new_state = tick(state, intent, world, *, in_water=..., in_lava=...)

The function never mutates its arguments. The Bot's 20 Hz physics
task calls it once per tick; offline unit tests call it manually to
verify gravity, friction, collision, step-up.

Constants are vanilla Minecraft Java Edition 1.20 values
(blocks/tick, where 1 tick = 50 ms):

- Gravity:                ``-0.08`` per tick²
- Air drag:               ``0.98`` per tick (vertical)
- Walk speed cap:         ``0.21`` blocks/tick (≈ 4.317 m/s)
- Sprint speed cap:       ``0.28`` blocks/tick
- Sneak speed cap:        ``0.06`` blocks/tick
- Ground friction:        slipperiness ``0.6`` (vanilla regular block)
- Water/lava drag:        ``0.8``
- Jump initial velocity:  ``0.42`` blocks/tick
- Step-up threshold:      ``0.6`` blocks (slab height)

Bot AABB is **0.6 × 1.8 × 0.6** centered on (x, z) with feet at y.
Per-axis swept collision is used (apply x, clamp; apply z, clamp;
apply y, clamp). This is the canonical vanilla approach.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Protocol

GRAVITY = -0.08
AIR_DRAG = 0.98
GROUND_FRICTION = 0.6
WATER_DRAG = 0.8
JUMP_VELOCITY = 0.42

WALK_CAP = 0.21
SPRINT_CAP = 0.28
SNEAK_CAP = 0.06

BBOX_W = 0.6   # full width on x and z
BBOX_H = 1.8   # height
STEP_HEIGHT = 0.6   # auto-step over slabs

TERMINAL_VELOCITY = -3.92


class CollisionWorld(Protocol):
    """World interface the physics needs. ``is_solid`` answers whether
    the *full block* at integer (bx, by, bz) is a collision body."""

    def is_solid(self, bx: int, by: int, bz: int) -> bool: ...


@dataclass(frozen=True, slots=True)
class PhysicsState:
    """Bot's kinematic state in world-space (feet position)."""

    x: float
    y: float
    z: float
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    on_ground: bool = False


@dataclass(frozen=True, slots=True)
class PhysicsIntent:
    """Desired motion for this tick (unit-ish vector + flags)."""

    dx: float = 0.0   # intended local strafe (-1..1)
    dz: float = 0.0   # intended local forward (-1..1)
    jump: bool = False
    sprint: bool = False
    sneak: bool = False


def _bbox_min_max(x: float, y: float, z: float) -> tuple[float, float, float, float, float, float]:
    """Return (x0, y0, z0, x1, y1, z1) of the bot AABB at feet (x, y, z)."""
    h = BBOX_W / 2
    return (x - h, y, z - h, x + h, y + BBOX_H, z + h)


def _intersects_solid(
    world: CollisionWorld, x: float, y: float, z: float
) -> bool:
    """Does the bot AABB at (x, y, z) intersect any solid block?"""
    x0, y0, z0, x1, y1, z1 = _bbox_min_max(x, y, z)
    # Integer block range the AABB overlaps. Use floor for min and
    # ceil-minus-1 for max (a value of exactly 5.0 is at block 5, not 4).
    bx0 = math.floor(x0)
    bx1 = math.floor(x1 - 1e-7)
    by0 = math.floor(y0)
    by1 = math.floor(y1 - 1e-7)
    bz0 = math.floor(z0)
    bz1 = math.floor(z1 - 1e-7)
    for by in range(by0, by1 + 1):
        for bz in range(bz0, bz1 + 1):
            for bx in range(bx0, bx1 + 1):
                if world.is_solid(bx, by, bz):
                    return True
    return False


def _resolve_axis(
    world: CollisionWorld,
    x: float, y: float, z: float,
    dx: float, dy: float, dz: float,
) -> tuple[float, bool]:
    """Move along a single axis and stop on collision.

    Returns ``(new_position_on_that_axis, collided)``.
    Only one of ``dx``, ``dy``, ``dz`` is non-zero.
    """
    target_x = x + dx
    target_y = y + dy
    target_z = z + dz
    if not _intersects_solid(world, target_x, target_y, target_z):
        if dx:
            return target_x, False
        if dy:
            return target_y, False
        return target_z, False

    # Bisect to find max safe travel. 8 iterations -> ≈ 0.004 block resolution
    # which is well below the BBOX/8 vanilla tolerance.
    lo, hi = 0.0, 1.0
    safe = 0.0
    for _ in range(8):
        mid = (lo + hi) / 2
        tx = x + dx * mid
        ty = y + dy * mid
        tz = z + dz * mid
        if _intersects_solid(world, tx, ty, tz):
            hi = mid
        else:
            safe = mid
            lo = mid
    if dx:
        return x + dx * safe, True
    if dy:
        return y + dy * safe, True
    return z + dz * safe, True


def _speed_cap(intent: PhysicsIntent, *, in_water: bool) -> float:
    if in_water:
        return WALK_CAP * 0.5
    if intent.sneak:
        return SNEAK_CAP
    if intent.sprint:
        return SPRINT_CAP
    return WALK_CAP


def tick(
    state: PhysicsState,
    intent: PhysicsIntent,
    world: CollisionWorld,
    *,
    in_water: bool = False,
    in_lava: bool = False,
) -> PhysicsState:
    """Advance the bot one tick (50 ms) and return the new state.

    Pure: ``state`` is not mutated; a new :class:`PhysicsState` is
    returned.
    """
    cap = _speed_cap(intent, in_water=in_water or in_lava)

    # 1) Horizontal intent → desired velocity (with cap normalisation).
    dx, dz = intent.dx, intent.dz
    mag = math.hypot(dx, dz)
    if mag > 1.0:
        dx /= mag
        dz /= mag
    target_vx = dx * cap
    target_vz = dz * cap

    # 2) Apply acceleration. On ground: snap to target * friction; in air:
    #    smaller acceleration so the bot retains momentum.
    if state.on_ground:
        accel = 0.5   # m/tick²: ground accel
    elif in_water or in_lava:
        accel = 0.2
    else:
        accel = 0.05
    vx = state.vx + (target_vx - state.vx) * accel
    vz = state.vz + (target_vz - state.vz) * accel

    # 3) Vertical: gravity & jump & buoyancy.
    vy = state.vy
    if intent.jump and (state.on_ground or in_water or in_lava):
        if in_water or in_lava:
            vy = 0.16
        else:
            vy = JUMP_VELOCITY
    vy += GRAVITY
    if in_water or in_lava:
        vy *= WATER_DRAG
    else:
        vy *= AIR_DRAG
    if vy < TERMINAL_VELOCITY:
        vy = TERMINAL_VELOCITY

    # 4) Per-axis swept collision: X, then Z, then Y.
    new_x, hit_x = _resolve_axis(world, state.x, state.y, state.z, vx, 0, 0)
    if hit_x:
        # Try step-up: if a single-step-up clears the block, raise feet.
        stepped_x, blocked_after = _resolve_axis(
            world, state.x, state.y + STEP_HEIGHT, state.z, vx, 0, 0,
        )
        if not blocked_after and stepped_x != state.x:
            # Now drop back down to the higher floor.
            new_x = stepped_x
            # Adjust y up; the y-axis resolve below will pin it.
            state = replace(state, y=state.y + STEP_HEIGHT)
        else:
            vx = 0.0
    new_z, hit_z = _resolve_axis(world, new_x, state.y, state.z, 0, 0, vz)
    if hit_z:
        stepped_z, blocked_after = _resolve_axis(
            world, new_x, state.y + STEP_HEIGHT, state.z, 0, 0, vz,
        )
        if not blocked_after and stepped_z != state.z:
            new_z = stepped_z
            state = replace(state, y=state.y + STEP_HEIGHT)
        else:
            vz = 0.0
    new_y, hit_y = _resolve_axis(world, new_x, state.y, new_z, 0, vy, 0)
    on_ground = False
    if hit_y:
        if vy < 0:
            on_ground = True
        vy = 0.0

    # 5) Apply ground friction next-tick (we apply it now to vx, vz).
    if on_ground and not (in_water or in_lava):
        vx *= GROUND_FRICTION
        vz *= GROUND_FRICTION

    return PhysicsState(
        x=new_x, y=new_y, z=new_z,
        vx=vx, vy=vy, vz=vz,
        on_ground=on_ground,
    )


__all__ = [
    "AIR_DRAG",
    "BBOX_H",
    "BBOX_W",
    "GRAVITY",
    "GROUND_FRICTION",
    "JUMP_VELOCITY",
    "SNEAK_CAP",
    "SPRINT_CAP",
    "STEP_HEIGHT",
    "TERMINAL_VELOCITY",
    "WALK_CAP",
    "WATER_DRAG",
    "CollisionWorld",
    "PhysicsIntent",
    "PhysicsState",
    "tick",
]
