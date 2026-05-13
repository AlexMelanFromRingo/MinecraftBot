"""String codec tests."""

from __future__ import annotations

import pytest
from minecraft_bot.codec import Reader, Writer, string
from minecraft_bot.errors import ValueOutOfRange

from ._fixtures import codec_fixtures


@pytest.mark.parametrize("fx", codec_fixtures("string"), ids=lambda fx: f"string:{fx['value']!r}")
def test_golden_round_trip(fx: dict) -> None:
    value = fx["value"]
    expected = bytes.fromhex(fx["hex"])
    w = Writer(); string.write(value, w)
    assert w.bytes() == expected
    assert string.read(Reader(expected)) == value


def test_unicode_round_trip() -> None:
    for v in ["", "a", "hello world", "Привет, мир!", "🎮🐍🌍", "a" * 100]:
        w = Writer(); string.write(v, w)
        assert string.read(Reader(w.bytes())) == v


def test_max_length_enforced() -> None:
    too_long = "x" * (string.MAX_LENGTH + 1)
    with pytest.raises(ValueOutOfRange):
        string.write(too_long, Writer())


def test_field_specific_max_length() -> None:
    with pytest.raises(ValueOutOfRange):
        string.write("ab", Writer(), max_length=1)
