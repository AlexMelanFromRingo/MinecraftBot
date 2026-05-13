"""VarLong codec tests."""

from __future__ import annotations

import pytest
from minecraft_bot.codec import Reader, Writer, varlong
from minecraft_bot.errors import OversizedVarInt, ValueOutOfRange

from ._fixtures import codec_fixtures


@pytest.mark.parametrize("fx", codec_fixtures("varlong"), ids=lambda fx: f"varlong:{fx['value']}")
def test_golden_round_trip(fx: dict) -> None:
    value = fx["value"]
    expected = bytes.fromhex(fx["hex"])
    w = Writer()
    varlong.write(value, w)
    assert w.bytes() == expected
    r = Reader(expected)
    assert varlong.read(r) == value
    assert r.remaining() == 0


def test_random_round_trip() -> None:
    import random
    rng = random.Random(0xDEADBEEF)
    for _ in range(200):
        v = rng.randint(-(1 << 63), (1 << 63) - 1)
        w = Writer(); varlong.write(v, w)
        assert varlong.read(Reader(w.bytes())) == v


def test_oversized_raises() -> None:
    bad = bytes([0xFF] * 10 + [0x80])
    with pytest.raises(OversizedVarInt):
        varlong.read(Reader(bad))


def test_out_of_range_encode() -> None:
    with pytest.raises(ValueOutOfRange):
        varlong.write(1 << 63, Writer())
    with pytest.raises(ValueOutOfRange):
        varlong.write(-(1 << 63) - 1, Writer())
