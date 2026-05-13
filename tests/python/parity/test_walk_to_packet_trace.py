"""T071 — Motion-shape parity Python <-> accel.

Both backends now drive `walk_to` through the 20 Hz physics tick.
A bot stepping toward the same target with the same `PhysicsIntent`
produces the same motion profile under both backends, modulo
floating-point ULP drift in the tick math.

This test runs the physics tick offline on synthesised floor worlds
under both backends and verifies:

- Final-x parity within 0.5 blocks.
- Tick-count parity within plus/minus 3 ticks.
- On-ground flag parity at every tick.
"""

from __future__ import annotations

import math


def _simulate_walk_python(start_x: float, target_x: float, n_ticks: int):
    """Drive Python physics ticks toward `target_x`. Returns
    (final_state, trace of (x, on_ground))."""
    from minecraft_bot.physics import PhysicsIntent, PhysicsState, tick

    class _FloorWorld:
        def is_solid(self, x: int, y: int, z: int) -> bool:
            return y == 0

    state = PhysicsState(x=start_x, y=1.0, z=0.5, on_ground=True)
    trace: list[tuple[float, bool]] = []
    for _ in range(n_ticks):
        dx = target_x - state.x
        mag = abs(dx)
        if mag < 1e-6:
            break
        intent = PhysicsIntent(dx=dx / mag, sprint=True)
        state = tick(state, intent, _FloorWorld())
        trace.append((state.x, state.on_ground))
    return state, trace


def _simulate_walk_accel(start_x: float, target_x: float, n_ticks: int):
    """Same simulation through the accel physics tick."""
    import json
    from pathlib import Path

    from minecraft_bot.codec import Reader
    from minecraft_bot.protocol.v763.packets.play.clientbound.map_chunk import (
        decode as pkt_decode,
    )
    from minecraft_bot_accel.physics import PhysicsIntent, PhysicsState, tick
    from minecraft_bot_accel.world import World

    REPO = Path(__file__).resolve().parents[3]
    raw_hex = json.loads(
        (REPO / "protocol-data/v763/golden_bytes/packets/clientbound/map_chunk.json").read_text()
    )[0]
    raw = bytes.fromhex(raw_hex)
    pkt = pkt_decode(Reader(raw))

    w = World()
    for cx in range(-1, 2):
        for cz in range(-1, 2):
            w.apply_map_chunk(pkt.payload, cx, cz)
            for x in range(cx * 16, cx * 16 + 16):
                for z in range(cz * 16, cz * 16 + 16):
                    for y in range(-32, 32):
                        w.apply_block_change(x, y, z, 0)
                    w.apply_block_change(x, 0, z, 1)

    state = PhysicsState(x=start_x, y=1.0, z=0.5, on_ground=True)
    trace: list[tuple[float, bool]] = []
    for _ in range(n_ticks):
        dx = target_x - state.x
        mag = abs(dx)
        if mag < 1e-6:
            break
        intent = PhysicsIntent(dx=dx / mag, sprint=True)
        state = tick(state, intent, w)
        trace.append((state.x, state.on_ground))
    return state, trace


def test_motion_shape_parity_straight_walk() -> None:
    """5-block straight walk: motion profile matches across backends."""
    n_ticks_budget = 60
    final_py, trace_py = _simulate_walk_python(0.5, 5.5, n_ticks_budget)
    final_ac, trace_ac = _simulate_walk_accel(0.5, 5.5, n_ticks_budget)

    print(
        f"\n  py ticks={len(trace_py)} final_x={final_py.x:.4f} "
        f"on_ground={final_py.on_ground}"
    )
    print(
        f"  ac ticks={len(trace_ac)} final_x={final_ac.x:.4f} "
        f"on_ground={final_ac.on_ground}"
    )

    assert math.isclose(
        final_py.x, final_ac.x, abs_tol=0.5
    ), f"final_x divergence: py={final_py.x} ac={final_ac.x}"

    assert abs(len(trace_py) - len(trace_ac)) <= 3, (
        f"tick-count divergence: py={len(trace_py)} ac={len(trace_ac)}"
    )

    # On-ground flag parity at every overlapping tick.
    for i, ((_px, pg), (_ax, ag)) in enumerate(zip(trace_py, trace_ac)):
        assert pg == ag, f"on_ground divergence at tick {i}: py={pg} ac={ag}"
