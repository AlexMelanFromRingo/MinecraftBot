"""Round-trip tests for UUID, Position, Identifier, BitSet codecs."""

from __future__ import annotations

import uuid as _uuid

import pytest
from minecraft_bot.codec import Reader, Writer, bitset, identifier, position, uuid
from minecraft_bot.errors import ValueOutOfRange

from ._fixtures import codec_fixtures

# --- uuid ------------------------------------------------------------------


@pytest.mark.parametrize("fx", codec_fixtures("uuid"), ids=lambda fx: f"uuid:{fx['value']}")
def test_uuid_golden(fx: dict) -> None:
    expected = bytes.fromhex(fx["hex"])
    val = _uuid.UUID(fx["value"])
    w = Writer(); uuid.write(val, w)
    assert w.bytes() == expected
    assert uuid.read(Reader(expected)) == val


def test_uuid_random() -> None:
    import random
    rng = random.Random(0xFEEDFACE)
    for _ in range(50):
        u = _uuid.UUID(int=rng.getrandbits(128))
        w = Writer(); uuid.write(u, w)
        assert uuid.read(Reader(w.bytes())) == u


# --- position --------------------------------------------------------------


@pytest.mark.parametrize("fx", codec_fixtures("position"), ids=lambda fx: f"pos:{fx['value']}")
def test_position_golden(fx: dict) -> None:
    val = tuple(fx["value"])
    expected = bytes.fromhex(fx["hex"])
    w = Writer(); position.write(val, w)
    assert w.bytes() == expected
    assert position.read(Reader(expected)) == val


def test_position_extremes() -> None:
    extremes = [
        (position.X_MAX, position.Y_MAX, position.Z_MAX),
        (position.X_MIN, position.Y_MIN, position.Z_MIN),
        (0, 0, 0),
    ]
    for v in extremes:
        w = Writer(); position.write(v, w)
        assert position.read(Reader(w.bytes())) == v


def test_position_out_of_range() -> None:
    with pytest.raises(ValueOutOfRange):
        position.write((position.X_MAX + 1, 0, 0), Writer())
    with pytest.raises(ValueOutOfRange):
        position.write((0, position.Y_MIN - 1, 0), Writer())


# --- identifier ------------------------------------------------------------


@pytest.mark.parametrize("fx", codec_fixtures("identifier"), ids=lambda fx: fx["value"])
def test_identifier_golden(fx: dict) -> None:
    expected = bytes.fromhex(fx["hex"])
    w = Writer(); identifier.write(fx["value"], w)
    assert w.bytes() == expected
    assert identifier.read(Reader(expected)) == fx["value"]


def test_identifier_default_namespace() -> None:
    """Decoding 'stone' produces 'minecraft:stone'."""
    from minecraft_bot.codec import string
    w = Writer(); string.write("stone", w)
    assert identifier.read(Reader(w.bytes())) == "minecraft:stone"


# --- bitset ----------------------------------------------------------------


@pytest.mark.parametrize("fx", codec_fixtures("bitset"), ids=lambda fx: f"bs:{fx['value']}")
def test_bitset_golden(fx: dict) -> None:
    val = set(fx["value"])
    expected = bytes.fromhex(fx["hex"])
    w = Writer(); bitset.write(val, w)
    assert w.bytes() == expected
    assert bitset.read(Reader(expected)) == val


def test_bitset_empty_is_one_byte() -> None:
    """Empty bitset = VarInt 0 = single 0x00 byte."""
    w = Writer(); bitset.write(set(), w)
    assert w.bytes() == b"\x00"
    assert bitset.read(Reader(w.bytes())) == set()


def test_bitset_negative_bit_index() -> None:
    with pytest.raises(ValueOutOfRange):
        bitset.write({-1}, Writer())
