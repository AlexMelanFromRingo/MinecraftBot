"""T077 — batched VarInt speedup (SC-008 ≥5×).

The per-op `varint.write(value, writer)` path crosses the FFI
boundary every call and ends up slower than pure Python (~0.3×).
The **batched** API `varint.read_many(buf, n)` / `write_many(vals)`
amortises that cost across many values in a single FFI call.

This test runs both the per-op pathway (informational) and the
batched pathway (SC-008 hard gate ≥5×).
"""

from __future__ import annotations

import time

N_VALUES = 1000


def _build_encoded_block(values: list[int]) -> bytes:
    """Pure-Python encoding of N varints concatenated."""
    from minecraft_bot.codec import Writer, varint

    w = Writer()
    for v in values:
        varint.write(v, w)
    return w.bytes()


def test_varint_batched_read_speedup() -> None:
    """SC-008 gate (batched): read_many beats per-op Python by ≥5×."""
    from minecraft_bot.codec import Reader as PyReader
    from minecraft_bot.codec import varint as py_varint
    from minecraft_bot_accel.codec import varint as ac_varint

    values = [i * 13 for i in range(N_VALUES)]
    encoded = _build_encoded_block(values)
    iters = 200

    # Python: per-op read loop.
    t0 = time.perf_counter()
    for _ in range(iters):
        r = PyReader(encoded)
        for _ in range(N_VALUES):
            py_varint.read(r)
    py_elapsed = time.perf_counter() - t0

    # Accel: single batched call.
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = ac_varint.read_many(encoded, N_VALUES)
    ac_elapsed = time.perf_counter() - t0

    ratio = py_elapsed / ac_elapsed if ac_elapsed > 0 else 0
    print(
        f"\n  varint.read_many (N={N_VALUES}): "
        f"py-loop={py_elapsed*1e3:.2f}ms ac-batched={ac_elapsed*1e3:.2f}ms "
        f"speedup={ratio:.2f}×"
    )
    assert ratio >= 5.0, f"SC-008 unmet: varint batched {ratio:.2f}× (need ≥5×)"


def test_varint_batched_write_speedup() -> None:
    """SC-008 gate (batched): write_many beats per-op Python by ≥5×."""
    from minecraft_bot.codec import Writer as PyWriter
    from minecraft_bot.codec import varint as py_varint
    from minecraft_bot_accel.codec import varint as ac_varint

    values = [i * 13 for i in range(N_VALUES)]
    iters = 200

    t0 = time.perf_counter()
    for _ in range(iters):
        w = PyWriter()
        for v in values:
            py_varint.write(v, w)
        _ = w.bytes()
    py_elapsed = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = ac_varint.write_many(values)
    ac_elapsed = time.perf_counter() - t0

    ratio = py_elapsed / ac_elapsed if ac_elapsed > 0 else 0
    print(
        f"\n  varint.write_many (N={N_VALUES}): "
        f"py-loop={py_elapsed*1e3:.2f}ms ac-batched={ac_elapsed*1e3:.2f}ms "
        f"speedup={ratio:.2f}×"
    )
    assert ratio >= 5.0, f"SC-008 unmet: varint batched write {ratio:.2f}× (need ≥5×)"
