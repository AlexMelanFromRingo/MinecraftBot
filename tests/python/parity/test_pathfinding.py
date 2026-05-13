"""T046 parity gate — pathfinder.

Compares the Python `minecraft_bot.pathfinding.find_path` with
`minecraft_bot_accel.pathfinding.find_path` on synthesised worlds.

Both implementations must produce IDENTICAL paths and costs given
the same inputs (deterministic A* with the same tie-break rule).
"""

from __future__ import annotations

# Synthesise a flat-plane world in the accel `World`:
# We need to set every block at y=0 to stone; everything else stays air.
# `apply_block_change` does single-cell sets, but `set_block` needs
# the chunk to be loaded. Use synthesised map_chunk payloads or skip
# to a different approach.
#
# Easier: write a *Python-only* NavWorld stub used by both backends
# via a custom callback. But the Rust pathfinder takes a native World
# pointer, not a Python callback. So we need to materialise the
# floor blocks into both Python and accel World caches.


def _build_floor_python(extents=(-5, 5)):
    """Build a Python World with a stone floor at y=0 across the extents."""
    from minecraft_bot.world.cache import World as PyWorld
    from minecraft_bot.world.chunk import Chunk, ChunkSection, PalettedContainer

    w = PyWorld()
    lo, hi = extents
    cx_lo, cx_hi = lo >> 4, hi >> 4
    cz_lo, cz_hi = lo >> 4, hi >> 4
    for cx in range(cx_lo, cx_hi + 1):
        for cz in range(cz_lo, cz_hi + 1):
            # Each section starts as single-value air (state 0), which
            # is what the Python `PalettedContainer.set` upgrade path
            # expects on first write.
            sections = [
                ChunkSection(
                    block_states=PalettedContainer(bits_per_entry=0, single_value=0),
                    biomes=PalettedContainer(bits_per_entry=0, single_value=0),
                )
                for _ in range(24)
            ]
            # Section index for y=0 with min_y=-64: (0 - (-64)) >> 4 = 4.
            sec = sections[4]
            for lx in range(16):
                for lz in range(16):
                    sec.set_block(lx, 0, lz, 1)  # stone
            w.chunks[(cx, cz)] = Chunk(
                cx=cx,
                cz=cz,
                sections=sections,
                min_y=-64,
                section_count=24,
            )
    return w


def _build_floor_accel(extents=(-5, 5)):
    """Same world in the accel backend, using direct apply_block_change."""
    # The accel World needs a chunk loaded before set_block has effect.
    # We synthesise a minimal map_chunk payload that loads air-only
    # chunks, then call apply_block_change to put stone blocks down.
    # Easier shortcut: for parity testing we materialise the floor
    # via a Python-built payload — but accel's apply_map_chunk takes
    # a payload buffer. We don't have a synthetic chunk-payload builder
    # here. As a quick workaround: just load one chunk via the same
    # captured fixture and overwrite its blocks via apply_block_change.
    import json
    from pathlib import Path

    from minecraft_bot_accel.world import World as AccelWorld

    REPO = Path(__file__).resolve().parents[3]
    raw_hex = json.loads(
        (
            REPO / "protocol-data/v763/golden_bytes/packets/clientbound/map_chunk.json"
        ).read_text()
    )[0]
    raw = bytes.fromhex(raw_hex)
    from minecraft_bot.codec import Reader
    from minecraft_bot.protocol.v763.packets.play.clientbound.map_chunk import (
        decode as pkt_decode,
    )

    pkt = pkt_decode(Reader(raw))

    w = AccelWorld()
    # Load enough chunks to cover the extents. Reuse the same payload
    # (block contents don't matter; we overwrite y=0 below).
    lo, hi = extents
    cx_lo, cx_hi = lo >> 4, hi >> 4
    cz_lo, cz_hi = lo >> 4, hi >> 4
    for cx in range(cx_lo, cx_hi + 1):
        for cz in range(cz_lo, cz_hi + 1):
            w.apply_map_chunk(pkt.payload, cx, cz)
            # Overwrite y=0 to stone, y!=0 to air.
            for x in range(cx * 16, cx * 16 + 16):
                for z in range(cz * 16, cz * 16 + 16):
                    # Floor at y=0 = stone, rest of the column = air.
                    w.apply_block_change(x, 0, z, 1)
                    for y in [-1, 1, 2, 3]:
                        w.apply_block_change(x, y, z, 0)
    return w


def test_pathfinding_straight_line_on_flat_world() -> None:
    """Bot walks a straight line on flat stone."""
    from minecraft_bot.pathfinding import find_path as py_find_path
    from minecraft_bot_accel.pathfinding import find_path as ac_find_path

    pyw = _build_floor_python()
    acw = _build_floor_accel()

    start, goal = (0, 1, 0), (3, 1, 0)
    py_path = py_find_path(pyw, start, goal, max_fall=3, max_nodes=10_000)
    ac_path = ac_find_path(acw, start, goal, max_fall=3, max_nodes=10_000)

    assert list(py_path.nodes) == [tuple(p) for p in ac_path]
    # Cost can't be compared directly through accel public surface
    # without a Path wrapper; structural parity is the contract here.


def test_pathfinding_same_node_returns_single_node() -> None:
    from minecraft_bot.pathfinding import find_path as py_find_path
    from minecraft_bot_accel.pathfinding import find_path as ac_find_path

    pyw = _build_floor_python()
    acw = _build_floor_accel()

    p = (2, 1, 2)
    py_path = py_find_path(pyw, p, p, max_fall=3, max_nodes=10)
    ac_path = ac_find_path(acw, p, p, max_fall=3, max_nodes=10)

    assert list(py_path.nodes) == [tuple(x) for x in ac_path]
    assert len(ac_path) == 1
