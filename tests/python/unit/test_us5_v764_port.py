"""US5 — Single-file port to a new protocol version (FR-016).

Demonstrates that adding a v764 packet:
1. Doesn't change v763's wire bytes.
2. Doesn't share v763's PACKET_ID space.
3. Co-exists in the codebase without touching v763 files.

The v764 directory contains exactly one demonstrative packet
(:mod:`minecraft_bot.protocol.v764.packets.play.clientbound.keep_alive`)
that modifies v763's keep_alive shape and ID. v763's keep_alive must
continue to pass its own round-trip test unchanged.
"""

from __future__ import annotations

from minecraft_bot.codec import Reader, Writer
from minecraft_bot.protocol import V_1_20_1, V_1_20_2
from minecraft_bot.protocol.v763.packets.play.clientbound import keep_alive as v763_ka
from minecraft_bot.protocol.v764.packets.play.clientbound import keep_alive as v764_ka


def test_v763_keep_alive_unchanged() -> None:
    """v763's keep_alive still has 8 bytes (single i64), id 0x23."""
    pkt = v763_ka.KeepAlive(keep_alive_id=42)
    w = Writer(); v763_ka.encode(pkt, w)
    encoded = w.bytes()
    assert len(encoded) == 8
    assert encoded.hex() == "000000000000002a"
    assert v763_ka.PACKET_ID == 0x23
    # Round-trip unchanged.
    assert v763_ka.decode(Reader(encoded)) == pkt


def test_v764_keep_alive_has_extra_field() -> None:
    """v764's keep_alive carries 12 bytes (i64 + i32) and uses id 0x24."""
    pkt = v764_ka.KeepAlive(keep_alive_id=42, deadline_ms=10000)
    w = Writer(); v764_ka.encode(pkt, w)
    encoded = w.bytes()
    assert len(encoded) == 12
    assert v764_ka.PACKET_ID == 0x24
    assert v764_ka.decode(Reader(encoded)) == pkt


def test_v763_and_v764_packet_ids_dont_collide() -> None:
    """The two versions live under different module paths and use
    different PACKET_IDs."""
    assert v763_ka.PACKET_ID != v764_ka.PACKET_ID
    assert v763_ka.KeepAlive is not v764_ka.KeepAlive
    assert v763_ka.__name__ != v764_ka.__name__


def test_protocol_versions_are_distinct() -> None:
    assert V_1_20_1.number == 763
    assert V_1_20_2.number == 764
    assert V_1_20_1 != V_1_20_2


def test_v763_classes_have_no_v764_counterpart_unless_overridden() -> None:
    """The v764 directory is sparse: only ``keep_alive`` is overridden;
    every other v763 packet would resolve through v763 unchanged in a
    future multi-version dispatcher. This test asserts the directory
    layout matches that expectation."""
    import os
    from pathlib import Path

    v764_root = Path(v764_ka.__file__).parent
    v764_packets = sorted(p.name for p in v764_root.glob("*.py") if not p.name.startswith("_"))
    assert v764_packets == ["keep_alive.py"], (
        f"expected exactly keep_alive.py in v764/play/clientbound/, found {v764_packets}"
    )
