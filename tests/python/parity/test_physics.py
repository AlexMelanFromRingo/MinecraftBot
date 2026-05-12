"""T046 parity gate — physics tick.

Compares `minecraft_bot.physics.tick` (Python reference) with
`minecraft_bot_accel.physics.tick` (PyO3 façade) on identical
inputs and asserts the resulting `PhysicsState` matches within
floating-point tolerance.
"""

from __future__ import annotations

import math

TOL = 1e-9


def _build_floor_python_world():
    """Build a `CollisionWorld`-compatible Python object with stone at y=0."""

    class _FloorWorld:
        def is_solid(self, x: int, y: int, z: int) -> bool:
            return y == 0

    return _FloorWorld()


def _build_floor_accel_world():
    """Build the same plane in the accel World."""
    import json
    from pathlib import Path
    from minecraft_bot.codec import Reader
    from minecraft_bot.protocol.v763.packets.play.clientbound.map_chunk import (
        decode as pkt_decode,
    )
    from minecraft_bot_accel.world import World

    REPO = Path(__file__).resolve().parents[3]
    raw_hex = json.loads(
        (
            REPO / "protocol-data/v763/golden_bytes/packets/clientbound/map_chunk.json"
        ).read_text()
    )[0]
    raw = bytes.fromhex(raw_hex)
    pkt = pkt_decode(Reader(raw))

    w = World()
    # Load a 3x3 chunk grid around origin. Floor at y=0, air everywhere
    # from y=-32 to y=320 to give the bot uncluttered fall space and
    # head clearance regardless of the captured chunk's natural terrain.
    for cx in range(-1, 2):
        for cz in range(-1, 2):
            w.apply_map_chunk(pkt.payload, cx, cz)
            for x in range(cx * 16, cx * 16 + 16):
                for z in range(cz * 16, cz * 16 + 16):
                    # Clear vertical column thoroughly.
                    for y in range(-32, 320):
                        w.apply_block_change(x, y, z, 0)
                    # Floor at y=0.
                    w.apply_block_change(x, 0, z, 1)
    return w


def test_gravity_parity_empty_world() -> None:
    """Gravity behaves identically with no floor."""
    from minecraft_bot.physics import (
        PhysicsIntent as PyIntent,
        PhysicsState as PyState,
        tick as py_tick,
    )
    from minecraft_bot_accel.physics import (
        PhysicsIntent as AcIntent,
        PhysicsState as AcState,
        tick as ac_tick,
    )

    class _Empty:
        def is_solid(self, x, y, z):
            return False

    py_state = PyState(x=0.0, y=10.0, z=0.0)
    ac_state = AcState(x=0.0, y=10.0, z=0.0)
    py_intent = PyIntent()
    ac_intent = AcIntent()

    # Accel takes a real `World` for collision; an empty World suffices.
    from minecraft_bot_accel.world import World as AcWorld

    empty_w = AcWorld()

    for _ in range(10):
        py_state = py_tick(py_state, py_intent, _Empty())
        ac_state = ac_tick(ac_state, ac_intent, empty_w)
        assert math.isclose(py_state.x, ac_state.x, abs_tol=TOL)
        assert math.isclose(py_state.y, ac_state.y, abs_tol=TOL)
        assert math.isclose(py_state.z, ac_state.z, abs_tol=TOL)
        assert math.isclose(py_state.vy, ac_state.vy, abs_tol=TOL)


def test_landing_parity() -> None:
    """Falling bot lands on the floor; both backends converge to y≈1."""
    from minecraft_bot.physics import (
        PhysicsIntent as PyIntent,
        PhysicsState as PyState,
        tick as py_tick,
    )
    from minecraft_bot_accel.physics import (
        PhysicsIntent as AcIntent,
        PhysicsState as AcState,
        tick as ac_tick,
    )

    py_world = _build_floor_python_world()
    ac_world = _build_floor_accel_world()

    py_state = PyState(x=0.5, y=5.0, z=0.5)
    ac_state = AcState(x=0.5, y=5.0, z=0.5)
    py_intent = PyIntent()
    ac_intent = AcIntent()

    for _ in range(100):
        py_state = py_tick(py_state, py_intent, py_world)
        ac_state = ac_tick(ac_state, ac_intent, ac_world)

    assert py_state.on_ground == ac_state.on_ground
    assert math.isclose(
        py_state.y, ac_state.y, abs_tol=1e-6
    ), f"y divergence: py={py_state.y} ac={ac_state.y}"


def test_horizontal_walk_parity() -> None:
    """One-tick walk forward gives same x displacement."""
    from minecraft_bot.physics import (
        PhysicsIntent as PyIntent,
        PhysicsState as PyState,
        tick as py_tick,
    )
    from minecraft_bot_accel.physics import (
        PhysicsIntent as AcIntent,
        PhysicsState as AcState,
        tick as ac_tick,
    )

    py_world = _build_floor_python_world()
    ac_world = _build_floor_accel_world()

    py_state = PyState(x=0.5, y=1.0, z=0.5, on_ground=True)
    ac_state = AcState(x=0.5, y=1.0, z=0.5, on_ground=True)
    py_intent = PyIntent(dx=1.0)
    ac_intent = AcIntent(dx=1.0)

    py_state = py_tick(py_state, py_intent, py_world)
    ac_state = ac_tick(ac_state, ac_intent, ac_world)

    assert math.isclose(
        py_state.x, ac_state.x, abs_tol=1e-6
    ), f"x divergence: py={py_state.x} ac={ac_state.x}"
    assert math.isclose(py_state.vx, ac_state.vx, abs_tol=1e-6)
