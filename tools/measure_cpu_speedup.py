#!/usr/bin/env python3
"""T082 + T085 — CPU footprint measurement (SC-012 / SC-013).

Runs identical chunk-decode + find_blocks_nearby workloads under both
backends, measuring user-CPU time via `resource.getrusage` (Linux/macOS)
or `time.process_time` (cross-platform fallback). Writes results to
`specs/003-rust-pyo3-bridge/research.md`'s Appendix A.

Usage:
    python tools/measure_cpu_speedup.py

This is an offline benchmark (no server). The live-arena variant
(SC-013) requires a Paper server and is exercised separately by
`tests/python/integration/test_hazard_arena_parity.py` once the
walk_to-via-physics revision lands.
"""

from __future__ import annotations

import json
import resource
import sys
import time
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
CHUNK_FIXTURE = REPO / "protocol-data/v763/golden_bytes/packets/clientbound/map_chunk.json"


def cpu_seconds() -> float:
    """Cumulative user+system CPU time for this process."""
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return ru.ru_utime + ru.ru_stime


def measure_chunk_decode_plus_query(payloads: list[bytes], rounds: int) -> dict:
    """End-to-end CPU benchmark mirroring chunk-streaming bursts the
    bot sees during normal play: decode payload + load into World
    cache + run find_blocks_nearby on the loaded data.

    Both backends do the same amount of *user-visible work*: the
    final World cache exposes a `get_block_id` / `find_blocks_nearby`
    surface.
    """
    sys.path.insert(0, str(REPO / "python"))
    from minecraft_bot.codec import Reader
    from minecraft_bot.protocol.v763.packets.play.clientbound.map_chunk import (
        decode as pkt_decode,
    )
    from minecraft_bot.world.cache import World as PyWorld
    from minecraft_bot_accel.world import World as AccelWorld

    class _PktAdapter:
        def __init__(self, p):
            self.payload = p.payload
            self.chunk_x = p.chunk_x
            self.chunk_z = p.chunk_z

    # Python pass: decode + load + query.
    t0_wall = time.perf_counter()
    t0_cpu = cpu_seconds()
    for _ in range(rounds):
        w = PyWorld()
        for raw in payloads:
            pkt = pkt_decode(Reader(raw))
            w.apply_map_chunk(_PktAdapter(pkt))
        # One find-nearby pass per round (typical bot query).
        origin = (payloads[0][0] * 16 + 8.0, 70.0, 0.0)
        _ = w.find_blocks_nearby("minecraft:stone", origin, radius=16, limit=16)
    py_wall = time.perf_counter() - t0_wall
    py_cpu = cpu_seconds() - t0_cpu

    # Accel pass: same workload through the accel surface.
    t0_wall = time.perf_counter()
    t0_cpu = cpu_seconds()
    for _ in range(rounds):
        w = AccelWorld()
        for raw in payloads:
            pkt = pkt_decode(Reader(raw))
            w.apply_map_chunk(pkt.payload, pkt.chunk_x, pkt.chunk_z)
        origin = (payloads[0][0] * 16 + 8.0, 70.0, 0.0)
        _ = w.find_blocks_nearby("minecraft:stone", origin, radius=16, limit=16)
    ac_wall = time.perf_counter() - t0_wall
    ac_cpu = cpu_seconds() - t0_cpu

    return {
        "rounds": rounds,
        "payloads_per_round": len(payloads),
        "python_wall_s": py_wall,
        "python_cpu_s": py_cpu,
        "accel_wall_s": ac_wall,
        "accel_cpu_s": ac_cpu,
        "cpu_drop_pct": (py_cpu - ac_cpu) / py_cpu * 100 if py_cpu > 0 else 0,
        "wall_speedup": py_wall / ac_wall if ac_wall > 0 else 0,
    }


def main() -> int:
    payloads_hex = json.loads(CHUNK_FIXTURE.read_text())
    payloads = [bytes.fromhex(h) for h in payloads_hex]

    print(f"Loaded {len(payloads)} captured chunks, mean size "
          f"{sum(len(p) for p in payloads) // len(payloads)} bytes")

    # Pick rounds so total work is ~5 seconds per backend.
    rounds = 200

    print(f"Running {rounds} rounds × {len(payloads)} chunks "
          f"= {rounds * len(payloads)} decode-and-query cycles per backend...")
    result = measure_chunk_decode_plus_query(payloads, rounds)

    print()
    print("Results")
    print("-------")
    print(f"  Python: wall={result['python_wall_s']:.3f}s  "
          f"cpu={result['python_cpu_s']:.3f}s")
    print(f"  Accel:  wall={result['accel_wall_s']:.3f}s  "
          f"cpu={result['accel_cpu_s']:.3f}s")
    print(f"  Wall speedup: {result['wall_speedup']:.2f}×")
    print(f"  CPU drop:     {result['cpu_drop_pct']:.1f}%")
    print()
    print(f"SC-012 (CPU drop ≥ 50% during chunk-streaming bursts):")
    print(f"  {'PASS' if result['cpu_drop_pct'] >= 50.0 else 'FAIL'}: "
          f"{result['cpu_drop_pct']:.1f}% drop")

    return 0 if result["cpu_drop_pct"] >= 50.0 else 1


if __name__ == "__main__":
    sys.exit(main())
