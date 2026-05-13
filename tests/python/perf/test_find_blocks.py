"""Performance: find_blocks_nearby < 100 ms over a populated chunk (SC-008)."""

from __future__ import annotations

from minecraft_bot.bot import Bot
from minecraft_bot.physics import PhysicsState
from minecraft_bot.protocol.v763.packets.play.clientbound.block_change import (
    BlockChange,
)


def _bot_with_logs() -> Bot:
    import struct

    from minecraft_bot.codec import Writer, nbt, varint
    from minecraft_bot.protocol.v763.packets.play.clientbound.map_chunk import (
        MapChunk,
    )

    bot = Bot.offline("h", 25565, "t")
    bot._has_initial_position = True
    bot._physics = PhysicsState(x=8.0, y=64.0, z=8.0, on_ground=True)
    w = Writer()
    nbt.write(nbt.NbtCompound(), w)
    sec_w = Writer()
    for _ in range(24):
        sec_w.write(struct.pack(">h", 0))
        sec_w.write(b"\x00")
        varint.write(0, sec_w)  # air
        varint.write(0, sec_w)
        sec_w.write(b"\x00")
        varint.write(1, sec_w)
        varint.write(0, sec_w)
    sec_bytes = sec_w.bytes()
    varint.write(len(sec_bytes), w)
    w.write(sec_bytes)
    varint.write(0, w)
    bot.world.apply_map_chunk(MapChunk(chunk_x=0, chunk_z=0, payload=w.bytes()))
    # Sprinkle oak_log state IDs (state 138 is oak_log y-axis variant).
    for dx in range(0, 10):
        for dz in range(0, 10):
            bot.world.apply_block_change(
                BlockChange(
                    location=(dx, 64, dz),
                    block_state_id=138,
                )
            )
    return bot


def test_find_blocks_nearby_fast(benchmark) -> None:
    bot = _bot_with_logs()
    result = benchmark(bot.find_blocks_nearby, "oak_log", radius=16, limit=5)
    stats = benchmark.stats.stats
    assert (
        stats.median < 0.1
    ), f"find_blocks median {stats.median*1000:.2f} ms exceeds 100 ms"
