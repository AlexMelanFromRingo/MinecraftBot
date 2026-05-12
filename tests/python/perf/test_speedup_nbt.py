"""T078 — NBT decode speedup benchmark (informational).

Accel doesn't yet expose a direct `nbt.read` PyO3 wrapper —
`minecraft_bot_accel.codec` ships varint + varlong only. NBT decode
happens INSIDE chunk_decode via the Rust crate, which the
chunk_decode benchmark (test_speedup_codecs.py) already covers
(2.84× faster on real captured 48 KiB payload).

This file records the NBT speedup target (SC-009 ≥10×) as a soft
informational test that imports both backends' NBT decoder and
runs a 1 KiB-ish synthetic payload through each. NBT decode is
exercised inside chunk_decode and was found there to be the
dominant time sink.

Hard SC-009 gate awaits a direct `accel.codec.nbt.read` wrap (a
batched API to amortise PyO3 boundary, mirroring R-005).
"""

from __future__ import annotations


import pytest


def _build_test_payload() -> bytes:
    """Hand-rolled small NBT compound — representative of the shapes
    the chunk decoder commonly encounters (network NBT root, mixed
    primitive children, no compound nesting)."""
    return bytes(
        [
            0x0A,  # TAG_Compound (network NBT root)
            0x01,
            0x00,
            0x05,
            *b"level",  # TAG_Byte "level" = 7
            0x07,
            0x03,
            0x00,
            0x06,
            *b"number",  # TAG_Int "number" = 42
            0x00,
            0x00,
            0x00,
            0x2A,
            0x08,
            0x00,
            0x04,
            *b"name",  # TAG_String "name" = "MC"
            0x00,
            0x02,
            *b"MC",
            0x00,  # TAG_End
        ]
    )


def test_nbt_decode_speedup_informational() -> None:
    """SC-009 (≥10× NBT decode) — measurement deferred.

    Accel doesn't expose `nbt.read` directly; the closest proxy is the
    full chunk-decode benchmark in test_speedup_codecs.py, where the
    2.84× speedup includes one NBT decode per section + one for the
    heightmaps NBT per chunk.

    Direct `accel.codec.nbt.read` wrap is a follow-on perf task —
    until then this test stays as a documentation marker.
    """
    pytest.skip(
        "NBT decode direct accel wrap not yet shipped; see "
        "test_speedup_codecs.py::test_chunk_decode_speedup for the "
        "encompassing measurement (2.84× faster, gates ≥2× soft)."
    )
