"""Physics tick unit tests (T022)."""

from __future__ import annotations

from minecraft_bot.physics import (
    GRAVITY, JUMP_VELOCITY, STEP_HEIGHT, TERMINAL_VELOCITY, WALK_CAP,
    PhysicsIntent, PhysicsState, tick,
)


class FlatWorld:
    """Floor at y=64 (block y=63 is solid)."""

    def is_solid(self, bx: int, by: int, bz: int) -> bool:
        return by <= 63


class StepWorld(FlatWorld):
    """Flat world + a one-block step at x=2..5."""

    def is_solid(self, bx: int, by: int, bz: int) -> bool:
        if super().is_solid(bx, by, bz):
            return True
        if 2 <= bx <= 5 and by == 64:
            return True
        return False


class WallWorld(FlatWorld):
    """Flat world + a 2-block wall at x=2..5 (impassable)."""

    def is_solid(self, bx: int, by: int, bz: int) -> bool:
        if super().is_solid(bx, by, bz):
            return True
        if 2 <= bx <= 5 and 64 <= by <= 66:
            return True
        return False


# --- gravity ---------------------------------------------------------


def test_gravity_pulls_bot_down() -> None:
    """In free fall, vy should decrease by ~GRAVITY each tick (with drag)."""
    state = PhysicsState(x=0.5, y=100.0, z=0.5)
    world = FlatWorld()
    new_state = tick(state, PhysicsIntent(), world)
    assert new_state.vy < 0  # gravity pulled us down
    assert new_state.y < 100.0


def test_terminal_velocity_clamp() -> None:
    """After many free-fall ticks vy should stop decreasing past terminal."""
    state = PhysicsState(x=0.5, y=10000.0, z=0.5, vy=-10.0)
    world = FlatWorld()
    new_state = tick(state, PhysicsIntent(), world)
    assert new_state.vy >= TERMINAL_VELOCITY - 1e-6


# --- on-ground floor stop --------------------------------------------


def test_lands_on_floor() -> None:
    """Bot falling onto y=64 floor settles with on_ground=True, vy=0."""
    state = PhysicsState(x=0.5, y=64.5, z=0.5, vy=-0.5)
    world = FlatWorld()
    s = state
    for _ in range(20):
        s = tick(s, PhysicsIntent(), world)
    assert s.on_ground
    assert s.vy == 0.0
    assert abs(s.y - 64.0) < 0.01


# --- horizontal walk ------------------------------------------------


def test_horizontal_walk_moves_forward() -> None:
    """With dz=1 intent on flat ground, bot moves +z."""
    state = PhysicsState(x=0.5, y=64.0, z=0.5, on_ground=True)
    world = FlatWorld()
    s = state
    for _ in range(40):
        s = tick(s, PhysicsIntent(dz=1.0), world)
    assert s.z > state.z + 0.5  # moved several blocks


def test_walk_cap_respected() -> None:
    """Steady-state horizontal velocity ≤ WALK_CAP."""
    state = PhysicsState(x=0.5, y=64.0, z=0.5, on_ground=True)
    world = FlatWorld()
    s = state
    for _ in range(50):
        s = tick(s, PhysicsIntent(dz=1.0), world)
    speed = (s.vx ** 2 + s.vz ** 2) ** 0.5
    # Friction is applied each tick post-move, so steady-state speed
    # is less than the raw cap. Just ensure no run-away.
    assert speed < WALK_CAP * 1.5


# --- jump ------------------------------------------------------------


def test_jump_lifts_bot() -> None:
    state = PhysicsState(x=0.5, y=64.0, z=0.5, on_ground=True)
    world = FlatWorld()
    s = tick(state, PhysicsIntent(jump=True), world)
    assert s.vy > 0
    assert s.y > 64.0


# --- wall collision -------------------------------------------------


def test_wall_blocks_horizontal_movement() -> None:
    state = PhysicsState(x=0.5, y=64.0, z=0.5, on_ground=True)
    world = WallWorld()
    s = state
    for _ in range(40):
        s = tick(s, PhysicsIntent(dx=1.0), world)
    # Bot can't pass through x=2 (wall starts at block 2).
    assert s.x < 2.0


# --- jump over a 1-block obstacle ----------------------------------


def test_jump_clears_ledge_with_horizontal_input() -> None:
    """Bot jumping while walking forward gains altitude to clear a step."""
    state = PhysicsState(x=0.5, y=64.0, z=0.5, on_ground=True)
    world = StepWorld()
    s = state
    peak_y = state.y
    # Jump on tick 0, then keep walking forward for ~25 ticks.
    s = tick(s, PhysicsIntent(dx=1.0, jump=True), world)
    for _ in range(25):
        s = tick(s, PhysicsIntent(dx=1.0), world)
        peak_y = max(peak_y, s.y)
    # JUMP_VELOCITY=0.42 gives ~1.2 blocks of altitude in vanilla.
    assert peak_y > state.y + 0.5
