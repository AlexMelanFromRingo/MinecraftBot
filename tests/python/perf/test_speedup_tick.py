"""T083 — Physics tick latency benchmark (Python vs accel).

Run `physics.tick` on a fixed PhysicsState/PhysicsIntent against a
simple floor world many times. Both backends are pure-function;
the speedup gate is SC-011 (≥2× faster).

Caveat: at the per-call FFI boundary the pure-Python tick is already
fast (~1.5 µs/call); PyO3 boundary overhead per accel call is
~0.5–1 µs. The SC-011 ≥2× target is reachable only when we batch
ticks inside Rust (e.g. ``physics.tick_n(state, intents, world)``);
the current per-call API is informational.
"""

from __future__ import annotations

import time


def _build_python_floor():
    class FloorWorld:
        def is_solid(self, x: int, y: int, z: int) -> bool:
            return y == 0

    return FloorWorld()


def _build_accel_floor():
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
    for cx in range(-1, 2):
        for cz in range(-1, 2):
            w.apply_map_chunk(pkt.payload, cx, cz)
            for x in range(cx * 16, cx * 16 + 16):
                for z in range(cz * 16, cz * 16 + 16):
                    for y in range(-32, 32):
                        w.apply_block_change(x, y, z, 0)
                    w.apply_block_change(x, 0, z, 1)
    return w


def test_tick_speedup_informational() -> None:
    """Compare physics.tick wall-clock between backends.

    Per-call PyO3 boundary cost dominates for ticks of this granularity;
    batched API needed to meet the SC-011 ≥2× target.
    """
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

    py_world = _build_python_floor()
    ac_world = _build_accel_floor()

    iters = 5000
    py_state = PyState(x=0.5, y=5.0, z=0.5)
    ac_state = AcState(x=0.5, y=5.0, z=0.5)
    py_intent = PyIntent()
    ac_intent = AcIntent()

    t0 = time.perf_counter()
    for _ in range(iters):
        py_state = py_tick(py_state, py_intent, py_world)
    py_elapsed = time.perf_counter() - t0
    print(
        f"\n  physics.tick py: {iters} iters in {py_elapsed*1e3:.2f} ms = "
        f"{py_elapsed*1e6/iters:.2f} µs/op"
    )

    t0 = time.perf_counter()
    for _ in range(iters):
        ac_state = ac_tick(ac_state, ac_intent, ac_world)
    ac_elapsed = time.perf_counter() - t0
    print(
        f"  physics.tick ac: {iters} iters in {ac_elapsed*1e3:.2f} ms = "
        f"{ac_elapsed*1e6/iters:.2f} µs/op"
    )

    ratio = py_elapsed / ac_elapsed if ac_elapsed > 0 else 0
    print(f"  per-tick speedup: {ratio:.2f}× (informational; per-call FFI dominates)")

    # Batched tick gate (SC-011 ≥ 2×). One FFI call drives N ticks
    # entirely in Rust with the lock-guarded chunk cache.
    from minecraft_bot_accel.physics import tick_n as ac_tick_n

    # Reset for a fair batched comparison.
    py_state = PyState(x=0.5, y=5.0, z=0.5)
    ac_state = AcState(x=0.5, y=5.0, z=0.5)
    batch_iters = 100
    batch_size = iters // batch_iters

    t0 = time.perf_counter()
    for _ in range(batch_iters):
        for _ in range(batch_size):
            py_state = py_tick(py_state, py_intent, py_world)
    py_batched_elapsed = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(batch_iters):
        ac_state = ac_tick_n(ac_state, ac_intent, ac_world, batch_size)
    ac_batched_elapsed = time.perf_counter() - t0

    batched_ratio = (
        py_batched_elapsed / ac_batched_elapsed if ac_batched_elapsed > 0 else 0
    )
    print(
        f"  batched (N={batch_size}/call): "
        f"py={py_batched_elapsed*1e3:.2f}ms ac={ac_batched_elapsed*1e3:.2f}ms "
        f"speedup={batched_ratio:.2f}× (SC-011 gate ≥2×)"
    )
    assert batched_ratio >= 2.0, (
        f"SC-011 unmet: batched physics tick {batched_ratio:.2f}× (need ≥2×)"
    )
