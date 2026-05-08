"""Framer tests — length-prefix, zlib threshold, fragmentation, errors."""

from __future__ import annotations

import zlib

import pytest

from minecraft_bot.framer import Framer, MAX_PACKET_SIZE
from minecraft_bot.errors import DecodeError, OversizedVarInt


# -------------------- compression disabled (threshold = -1) ----------------


def test_uncompressed_round_trip() -> None:
    fr_tx = Framer(compression_threshold=-1)
    fr_rx = Framer(compression_threshold=-1)
    body = b"\x00abcdef"
    framed = fr_tx.encode(body)
    fr_rx.feed(framed)
    assert fr_rx.try_extract() == body
    assert fr_rx.try_extract() is None


def test_uncompressed_back_to_back_packets() -> None:
    fr_tx = Framer(compression_threshold=-1)
    fr_rx = Framer(compression_threshold=-1)
    bodies = [b"\x00first", b"\x00second_packet", b"\x00", b"\x00x" * 100]
    blob = b"".join(fr_tx.encode(b) for b in bodies)
    fr_rx.feed(blob)
    out = []
    while True:
        b = fr_rx.try_extract()
        if b is None:
            break
        out.append(b)
    assert out == bodies


def test_uncompressed_tcp_fragmentation() -> None:
    """A single packet split across many feed() calls is reassembled."""
    fr_tx = Framer(compression_threshold=-1)
    fr_rx = Framer(compression_threshold=-1)
    body = b"\x00" + b"X" * 500
    framed = fr_tx.encode(body)
    # Feed 1 byte at a time
    for i in range(len(framed)):
        chunk = framed[i:i + 1]
        fr_rx.feed(chunk)
        if i < len(framed) - 1:
            assert fr_rx.try_extract() is None, f"premature extract at byte {i}"
    assert fr_rx.try_extract() == body


# -------------------- compression enabled (threshold >= 0) -----------------


def test_compressed_threshold_0_compresses_all() -> None:
    fr_tx = Framer(compression_threshold=0)
    fr_rx = Framer(compression_threshold=0)
    body = b"\x00small"
    framed = fr_tx.encode(body)
    fr_rx.feed(framed)
    assert fr_rx.try_extract() == body


def test_compressed_threshold_below_payload_uses_compression() -> None:
    fr_tx = Framer(compression_threshold=10)
    fr_rx = Framer(compression_threshold=10)
    body = b"\x00" + b"A" * 100  # well above threshold; will compress
    framed = fr_tx.encode(body)
    # Inner data_length should be 101 (the uncompressed body length)
    fr_rx.feed(framed)
    assert fr_rx.try_extract() == body


def test_compressed_threshold_above_payload_uncompressed_inner() -> None:
    fr_tx = Framer(compression_threshold=256)
    fr_rx = Framer(compression_threshold=256)
    body = b"\x00small_body"
    framed = fr_tx.encode(body)
    # In this mode inner data_length is 0 (no compression applied) —
    # validate by checking decode round-trip.
    fr_rx.feed(framed)
    assert fr_rx.try_extract() == body


def test_compressed_round_trip_random() -> None:
    import random
    rng = random.Random(0xCAFE)
    for _ in range(20):
        threshold = rng.choice([-1, 0, 64, 256, 1024])
        fr_tx = Framer(compression_threshold=threshold)
        fr_rx = Framer(compression_threshold=threshold)
        n_packets = rng.randint(1, 8)
        bodies = []
        for _ in range(n_packets):
            size = rng.randint(1, 2048)
            bodies.append(bytes(rng.randint(0, 255) for _ in range(size)))
        blob = b"".join(fr_tx.encode(b) for b in bodies)
        fr_rx.feed(blob)
        out = []
        while True:
            b = fr_rx.try_extract()
            if b is None:
                break
            out.append(b)
        assert out == bodies


# -------------------- threshold mid-session change ------------------------


def test_threshold_can_change_mid_stream() -> None:
    """Receiver respects threshold change after SetCompression packet."""
    fr_rx = Framer(compression_threshold=-1)

    # First packet uncompressed.
    fr_tx_a = Framer(compression_threshold=-1)
    fr_rx.feed(fr_tx_a.encode(b"\x00first"))
    assert fr_rx.try_extract() == b"\x00first"

    # Server sends SetCompression; threshold flips on both sides.
    fr_rx.compression_threshold = 64
    fr_tx_b = Framer(compression_threshold=64)
    fr_rx.feed(fr_tx_b.encode(b"\x00" + b"B" * 200))
    assert fr_rx.try_extract() == b"\x00" + b"B" * 200


# -------------------- error paths -----------------------------------------


def test_oversized_outer_varint_raises() -> None:
    fr = Framer()
    fr.feed(b"\xff\xff\xff\xff\xff\x80")  # 6 bytes with continuation
    with pytest.raises(OversizedVarInt):
        fr.try_extract()


def test_packet_length_above_cap_raises() -> None:
    fr = Framer()
    # Encode a varint length greater than MAX_PACKET_SIZE.
    huge = MAX_PACKET_SIZE + 1
    from minecraft_bot.codec import Writer, varint
    w = Writer(); varint.write(huge, w)
    fr.feed(w.bytes())
    with pytest.raises(DecodeError, match="exceeds MAX_PACKET_SIZE"):
        fr.try_extract()


def test_corrupted_zlib_raises() -> None:
    fr = Framer(compression_threshold=10)
    # Build a fake frame with declared data_length=100 but garbage zlib
    from minecraft_bot.codec import Writer, varint
    inner_w = Writer(); varint.write(100, inner_w)
    inner = inner_w.bytes() + b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09"
    outer_w = Writer(); varint.write(len(inner), outer_w)
    fr.feed(outer_w.bytes() + inner)
    with pytest.raises(DecodeError, match="zlib decompress failed"):
        fr.try_extract()


def test_decompressed_size_mismatch_raises() -> None:
    fr = Framer(compression_threshold=10)
    # Compress 50-byte body but declare data_length = 999.
    body = b"X" * 50
    compressed = zlib.compress(body)
    from minecraft_bot.codec import Writer, varint
    inner_w = Writer(); varint.write(999, inner_w)
    inner = inner_w.bytes() + compressed
    outer_w = Writer(); varint.write(len(inner), outer_w)
    fr.feed(outer_w.bytes() + inner)
    with pytest.raises(DecodeError, match="decompressed size"):
        fr.try_extract()


def test_empty_buffer_returns_none() -> None:
    assert Framer().try_extract() is None


def test_single_zero_byte_no_payload() -> None:
    """A zero-length packet (legal-but-pointless) is decoded as empty body."""
    fr = Framer(compression_threshold=-1)
    fr.feed(b"\x00")
    assert fr.try_extract() == b""
