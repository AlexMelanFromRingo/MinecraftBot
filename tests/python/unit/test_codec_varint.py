"""VarInt codec tests — round-trip, golden bytes, error paths."""

from __future__ import annotations

import pytest
from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.errors import IncompleteRead, OversizedVarInt, ValueOutOfRange

from ._fixtures import codec_fixtures


@pytest.mark.parametrize("fx", codec_fixtures("varint"), ids=lambda fx: f"varint:{fx['value']}")
def test_golden_round_trip(fx: dict) -> None:
    """encode(value) == golden hex; decode(golden hex) == value."""
    value = fx["value"]
    expected = bytes.fromhex(fx["hex"])

    w = Writer()
    varint.write(value, w)
    assert w.bytes() == expected, f"encode({value!r}) wrong"

    r = Reader(expected)
    assert varint.read(r) == value
    assert r.remaining() == 0, "did not consume all bytes"


def test_round_trip_random_values() -> None:
    import random
    rng = random.Random(0xCAFEBABE)
    for _ in range(200):
        v = rng.randint(-(1 << 31), (1 << 31) - 1)
        w = Writer()
        varint.write(v, w)
        r = Reader(w.bytes())
        assert varint.read(r) == v


def test_oversized_varint_raises() -> None:
    """Six bytes with continuation bit on every one is oversized."""
    bad = bytes([0xFF] * 5 + [0x80])
    r = Reader(bad)
    with pytest.raises(OversizedVarInt):
        varint.read(r)


def test_oversized_varint_byte_count() -> None:
    bad = bytes([0xFF] * 5 + [0x01])
    r = Reader(bad)
    with pytest.raises(OversizedVarInt) as exc:
        varint.read(r)
    assert exc.value.byte_count == 6


def test_truncated_input_raises_incomplete() -> None:
    r = Reader(bytes([0xFF, 0xFF]))  # continuation set, then EOF
    with pytest.raises(IncompleteRead):
        varint.read(r)


@pytest.mark.parametrize("v", [(1 << 31), -(1 << 31) - 1, 1 << 40])
def test_out_of_range_raises_on_encode(v: int) -> None:
    with pytest.raises(ValueOutOfRange):
        varint.write(v, Writer())


def test_zero_is_one_byte() -> None:
    w = Writer()
    varint.write(0, w)
    assert w.bytes() == b"\x00"


def test_encoded_size() -> None:
    assert varint.encoded_size(0) == 1
    assert varint.encoded_size(127) == 1
    assert varint.encoded_size(128) == 2
    assert varint.encoded_size(2147483647) == 5
    assert varint.encoded_size(-1) == 5  # negative always 5 bytes
