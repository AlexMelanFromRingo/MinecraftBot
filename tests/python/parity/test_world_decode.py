"""T046 parity gate — World cache + decode_chunk + classification.

Compares `minecraft_bot` (Python reference) vs
`minecraft_bot_accel.world` (PyO3 façade) on real captured payloads.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
FIXTURE = REPO / "protocol-data/v763/golden_bytes/packets/clientbound/map_chunk.json"


def _load_payloads() -> list[bytes]:
    raw = json.loads(FIXTURE.read_text())
    return [bytes.fromhex(h) for h in raw]


@pytest.fixture(scope="module")
def captured_payloads() -> list[bytes]:
    if not FIXTURE.exists():
        pytest.skip(f"fixture missing: {FIXTURE}")
    return _load_payloads()


def _decode_python(raw: bytes) -> tuple[int, int, int, int]:
    """Return (sections, block_entities, cx, cz) plus state at (0,0)."""
    from minecraft_bot.codec import Reader
    from minecraft_bot.protocol.v763.packets.play.clientbound.map_chunk import decode as pkt_decode
    from minecraft_bot.world.decode_chunk import decode as chunk_decode

    pkt = pkt_decode(Reader(raw))
    chunk = chunk_decode(pkt.payload, cx=pkt.chunk_x, cz=pkt.chunk_z)
    return (
        len(chunk.sections),
        len(chunk.block_entities),
        pkt.chunk_x,
        pkt.chunk_z,
    )


def _decode_accel(raw: bytes) -> tuple[int, int, int, int]:
    from minecraft_bot.codec import Reader  # parsing the OUTER packet header still uses Python; accel exposes the inner decoder
    from minecraft_bot.protocol.v763.packets.play.clientbound.map_chunk import decode as pkt_decode
    from minecraft_bot_accel.world import decode_chunk_summary

    pkt = pkt_decode(Reader(raw))
    sections, be_count, _first = decode_chunk_summary(
        pkt.payload, pkt.chunk_x, pkt.chunk_z, -64, 24
    )
    return (sections, be_count, pkt.chunk_x, pkt.chunk_z)


def test_decode_chunk_parity_all_fixtures(captured_payloads: list[bytes]) -> None:
    """For every captured map_chunk fixture, Python and accel agree on
    section count, block-entity count, and chunk coordinates."""
    for i, raw in enumerate(captured_payloads):
        py_result = _decode_python(raw)
        ac_result = _decode_accel(raw)
        assert py_result == ac_result, (
            f"fixture {i}: python={py_result} accel={ac_result}"
        )


def test_world_apply_map_chunk_loads_chunk_with_correct_count(
    captured_payloads: list[bytes],
) -> None:
    """Loading payloads via accel `World.apply_map_chunk` populates the cache."""
    from minecraft_bot.codec import Reader
    from minecraft_bot.protocol.v763.packets.play.clientbound.map_chunk import decode as pkt_decode
    from minecraft_bot_accel.world import World

    w = World()
    assert w.loaded_chunk_count() == 0
    for raw in captured_payloads:
        pkt = pkt_decode(Reader(raw))
        cx, cz = w.apply_map_chunk(pkt.payload, pkt.chunk_x, pkt.chunk_z)
        assert (cx, cz) == (pkt.chunk_x, pkt.chunk_z)
    assert w.loaded_chunk_count() == len(captured_payloads)


def test_block_classification_parity() -> None:
    """`block_table` predicates agree between Python and accel for
    a sample of common block states."""
    from minecraft_bot.world import block_table as py_tbl
    from minecraft_bot_accel.world import block_is_solid, block_is_water, block_name

    # state_id 0 = air, 1 = stone, 79 = (some natural block).
    for sid in [0, 1, 2, 8, 79, 100, 1000, 22450]:
        assert py_tbl.is_solid(sid) == block_is_solid(sid), \
            f"is_solid divergence at state_id={sid}"
        assert py_tbl.is_water(sid) == block_is_water(sid), \
            f"is_water divergence at state_id={sid}"
        assert py_tbl.get_name(sid) == block_name(sid), \
            f"get_name divergence at state_id={sid}"


def test_find_blocks_nearby_parity_on_loaded_world(
    captured_payloads: list[bytes],
) -> None:
    """find_blocks_nearby on a populated world returns the same matches
    in Python and accel (after loading the same chunks into both)."""
    from minecraft_bot.codec import Reader
    from minecraft_bot.protocol.v763.packets.play.clientbound.map_chunk import decode as pkt_decode
    from minecraft_bot.world.cache import World as PyWorld
    from minecraft_bot_accel.world import World as AccelWorld

    pyw = PyWorld()
    acw = AccelWorld()
    chunk_keys: list[tuple[int, int]] = []
    for raw in captured_payloads:
        pkt = pkt_decode(Reader(raw))
        # Load into Python ref using a synthesised packet object.
        chunk_keys.append((pkt.chunk_x, pkt.chunk_z))

        class _PktAdapter:
            def __init__(self, p):
                self.payload = p.payload
                self.chunk_x = p.chunk_x
                self.chunk_z = p.chunk_z
        pyw.apply_map_chunk(_PktAdapter(pkt))
        acw.apply_map_chunk(pkt.payload, pkt.chunk_x, pkt.chunk_z)

    # Pick the centre of the first chunk as origin.
    cx, cz = chunk_keys[0]
    origin = (float(cx * 16 + 8), 70.0, float(cz * 16 + 8))

    # Look for "minecraft:stone" — common in deep underground.
    py_matches = pyw.find_blocks_nearby("minecraft:stone", origin, radius=16, limit=8)
    ac_matches = acw.find_blocks_nearby("minecraft:stone", origin, radius=16, limit=8)
    assert py_matches == ac_matches, (
        f"find_blocks_nearby divergence:\n  python={py_matches}\n  accel={ac_matches}"
    )
