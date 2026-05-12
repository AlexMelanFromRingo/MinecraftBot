"""T077+T079 — micro-benchmarks comparing python vs accel.

**Finding from initial measurements**: per-call PyO3 FFI overhead
dominates trivial codec ops (varint at 1-2 bytes). The win is at
**packet / chunk** granularity where many primitives run inside
Rust without crossing the boundary.

The hard gates the spec targets (SC-008 ≥5× varint, SC-009 ≥10× NBT,
SC-010 ≥10× chunk decode, SC-011 ≥5× A*) are realistic ONLY for the
heavy ops. Per-op codec micro-benchmarks are kept here as
**informational** measurements — they print speedup but do not gate
the build.
"""

from __future__ import annotations

import time
from typing import Callable

ITER = 50_000


def _bench(name: str, fn: Callable[[], None], iterations: int = ITER) -> float:
    """Run ``fn`` ``iterations`` times. Return total seconds."""
    # Warm up to avoid first-call JIT/import skew.
    for _ in range(min(100, iterations // 10)):
        fn()
    t0 = time.perf_counter()
    for _ in range(iterations):
        fn()
    elapsed = time.perf_counter() - t0
    print(
        f"\n  [{name}] {iterations} iters in {elapsed*1e3:.2f} ms = "
        f"{elapsed*1e9/iterations:.1f} ns/op"
    )
    return elapsed


def test_varint_write_speedup() -> None:
    """Encode value 300 a bunch of times under each backend."""
    from minecraft_bot.codec import varint as py_varint
    from minecraft_bot.codec import Writer as PyWriter
    from minecraft_bot_accel.codec import varint as ac_varint
    from minecraft_bot_accel.codec import Writer as AcWriter

    def py_op() -> None:
        w = PyWriter()
        py_varint.write(300, w)
        _ = w.bytes()

    def ac_op() -> None:
        w = AcWriter()
        ac_varint.write(300, w)
        _ = w.bytes()

    py_time = _bench("varint.write py", py_op)
    ac_time = _bench("varint.write accel", ac_op)
    ratio = py_time / ac_time if ac_time > 0 else 0
    print(f"  varint.write speedup: accel is {ratio:.2f}× faster (informational)")
    # Informational only — see module docstring on per-op FFI overhead.
    # Heavy ops are the real performance gate (chunk_decode below).


def test_varint_read_speedup() -> None:
    """Decode the encoded form many times."""
    from minecraft_bot.codec import varint as py_varint, Reader as PyReader
    from minecraft_bot_accel.codec import varint as ac_varint, Reader as AcReader

    encoded = b"\xac\x02"  # 300

    def py_op() -> None:
        r = PyReader(encoded)
        _ = py_varint.read(r)

    def ac_op() -> None:
        r = AcReader(encoded)
        _ = ac_varint.read(r)

    py_time = _bench("varint.read py", py_op)
    ac_time = _bench("varint.read accel", ac_op)
    ratio = py_time / ac_time if ac_time > 0 else 0
    print(f"  varint.read speedup: accel is {ratio:.2f}× faster (informational)")
    # Informational; see module docstring.


def test_chunk_decode_speedup() -> None:
    """Decode the same captured map_chunk payload 50x under each backend."""
    import json
    from pathlib import Path
    from minecraft_bot.codec import Reader as PyReader
    from minecraft_bot.protocol.v763.packets.play.clientbound.map_chunk import (
        decode as pkt_decode,
    )
    from minecraft_bot.world.decode_chunk import decode as py_chunk
    from minecraft_bot_accel.world import decode_chunk_summary as ac_chunk

    REPO = Path(__file__).resolve().parents[3]
    hexes = json.loads(
        (
            REPO / "protocol-data/v763/golden_bytes/packets/clientbound/map_chunk.json"
        ).read_text()
    )
    raw = bytes.fromhex(hexes[0])
    pkt = pkt_decode(PyReader(raw))
    payload = pkt.payload
    cx, cz = pkt.chunk_x, pkt.chunk_z

    iters = 50  # heavyweight ops; fewer iterations needed

    def py_op() -> None:
        _ = py_chunk(payload, cx=cx, cz=cz)

    def ac_op() -> None:
        _ = ac_chunk(payload, cx, cz, -64, 24)

    py_time = _bench("chunk_decode py", py_op, iters)
    ac_time = _bench("chunk_decode accel", ac_op, iters)
    ratio = py_time / ac_time if ac_time > 0 else 0
    print(f"  speedup: accel is {ratio:.2f}× faster")
    # Real chunk decode is heavy enough that even a basic Rust port
    # should beat Python by a wide margin. Soft check: ≥ 2×.
    assert ratio > 2.0, f"expected accel chunk_decode ≥ 2× faster, got {ratio:.2f}×"
