"""Performance: Bot.tick() median ≤ 5 ms, p99 ≤ 25 ms (SC-009)."""

from __future__ import annotations

import pytest

from minecraft_bot.bot import Bot
from minecraft_bot.physics import PhysicsIntent, PhysicsState
from minecraft_bot.protocol.v763.packets.play.clientbound.map_chunk import (
    MapChunk,
)


def _bot_with_one_loaded_chunk() -> Bot:
    """Bot with initial position set + a tiny synthetic chunk under feet."""
    import struct
    from minecraft_bot.codec import Writer, nbt, varint

    bot = Bot.offline("h", 25565, "t")
    bot._has_initial_position = True
    bot._physics = PhysicsState(x=8.0, y=64.0, z=8.0, on_ground=True)
    # Build a one-chunk "all stone" payload so collision works.
    w = Writer()
    nbt.write(nbt.NbtCompound(), w)
    sec_w = Writer()
    for _ in range(24):
        sec_w.write(struct.pack(">h", 4096))
        sec_w.write(b"\x00")
        varint.write(1, sec_w)   # stone
        varint.write(0, sec_w)
        sec_w.write(b"\x00")
        varint.write(1, sec_w)
        varint.write(0, sec_w)
    sec_bytes = sec_w.bytes()
    varint.write(len(sec_bytes), w)
    w.write(sec_bytes)
    varint.write(0, w)
    bot.world.apply_map_chunk(MapChunk(chunk_x=0, chunk_z=0, payload=w.bytes()))
    # Active intent so the tick actually runs physics.
    bot._intent = PhysicsIntent(dx=1.0, dz=0.0, sprint=True)
    return bot


def test_tick_median_under_5ms(benchmark) -> None:
    bot = _bot_with_one_loaded_chunk()
    benchmark(bot.tick)
    stats = benchmark.stats.stats
    # pytest-benchmark stores 'median' in seconds.
    assert stats.median < 0.005, f"tick median {stats.median*1000:.2f} ms exceeds 5 ms"
