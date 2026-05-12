"""T071 (companion) — typed packet hooks via accel Bot.on_packet.

The accel `Bot` exposes `on_packet(packet_id, callback)` so users
can subscribe to specific clientbound packets. Hooks receive the
raw body bytes; to recover the typed dataclass, route through the
Python reference's decoders (the typed dataclass surface lives in
`minecraft_bot.protocol.v763.packets`).

This test exercises the registration + dispatch path offline by
feeding synthesised packet bodies through a connected Bot.
"""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.live


async def test_accel_on_packet_fires_for_map_chunk(live_server) -> None:
    """Connect, register hooks for 0x24 (map_chunk) and 0x57
    (update_health), confirm at least one map_chunk fires within
    the chunk-streaming burst."""
    import minecraft_bot_accel as mb

    bot = mb.Bot.offline(live_server.host, live_server.port, "HookBot1")

    fired: dict[int, int] = {}

    def cb(packet_id: int, body: bytes) -> None:
        fired[packet_id] = fired.get(packet_id, 0) + 1

    await bot.on_packet(0x24, cb)  # map_chunk
    await bot.on_packet(0x57, cb)  # update_health

    await bot.connect()
    try:
        for _ in range(40):
            if bot.loaded_chunk_count() > 5:
                break
            await asyncio.sleep(0.25)
        # Give the dispatcher a moment.
        await asyncio.sleep(1.5)

        assert fired.get(0x24, 0) > 0, (
            f"expected at least one map_chunk hook to fire; got {fired}"
        )
        print(f"\n[hooks] fired: {fired}")
    finally:
        await bot.disconnect()


async def test_accel_typed_decode_via_python_reference(live_server) -> None:
    """Typical bot recipe: capture a packet body in an accel hook,
    decode through the Python reference's typed decoder, inspect the
    parsed fields. Validates the suggested integration pattern from
    docs/migration_to_accel.md."""
    import minecraft_bot_accel as mb
    from minecraft_bot.codec import Reader
    from minecraft_bot.protocol.v763.packets.play.clientbound.map_chunk import (
        decode as map_chunk_decode,
    )

    bot = mb.Bot.offline(live_server.host, live_server.port, "HookBot2")

    parsed: list[tuple[int, int]] = []  # captured (chunk_x, chunk_z)

    def cb(packet_id: int, body: bytes) -> None:
        pkt = map_chunk_decode(Reader(body))
        parsed.append((pkt.chunk_x, pkt.chunk_z))

    await bot.on_packet(0x24, cb)
    await bot.connect()
    try:
        for _ in range(60):
            if len(parsed) > 0:
                break
            await asyncio.sleep(0.25)
        assert parsed, "no map_chunk decoded in hook"
        cx, cz = parsed[0]
        assert isinstance(cx, int) and isinstance(cz, int)
        print(f"\n[hooks] first chunk decoded via python ref: ({cx}, {cz})")
    finally:
        await bot.disconnect()
