"""T070 — Packet/codec encode parity Python ↔ accel.

For codecs the accel package exposes (varint + varlong as of now),
encode the same values under both backends and assert byte equality.

Full per-packet parity ships once `python-ext/src/protocol/` lands
(T055). Until then this test guards the codec subset that's live.
"""

from __future__ import annotations

import pytest

VARINT_TEST_VALUES = [
    0,
    1,
    2,
    127,
    128,
    255,
    300,
    25565,
    2147483647,
    -1,
    -128,
    -1000,
    -2147483648,
]

VARLONG_TEST_VALUES = VARINT_TEST_VALUES + [
    1 << 31,
    1 << 40,
    (1 << 63) - 1,
    -(1 << 63),
]


@pytest.mark.parametrize("value", VARINT_TEST_VALUES)
def test_varint_write_byte_parity(value: int) -> None:
    from minecraft_bot.codec import Writer as PyWriter
    from minecraft_bot.codec import varint as py_varint
    from minecraft_bot_accel.codec import Writer as AcWriter
    from minecraft_bot_accel.codec import varint as ac_varint

    pw = PyWriter()
    py_varint.write(value, pw)
    py_bytes = pw.bytes()

    aw = AcWriter()
    ac_varint.write(value, aw)
    ac_bytes = aw.bytes()

    assert (
        py_bytes == ac_bytes
    ), f"varint.write({value}) divergence: py={py_bytes.hex()} ac={ac_bytes.hex()}"


@pytest.mark.parametrize("value", VARINT_TEST_VALUES)
def test_varint_read_value_parity(value: int) -> None:
    """Encode in Python, decode in accel: same value back."""
    from minecraft_bot.codec import Writer as PyWriter
    from minecraft_bot.codec import varint as py_varint
    from minecraft_bot_accel.codec import Reader as AcReader
    from minecraft_bot_accel.codec import varint as ac_varint

    pw = PyWriter()
    py_varint.write(value, pw)
    encoded = pw.bytes()

    ar = AcReader(encoded)
    decoded = ac_varint.read(ar)
    assert decoded == value, f"py-encoded {value} decoded as {decoded} on accel"


@pytest.mark.parametrize("value", VARLONG_TEST_VALUES)
def test_varlong_write_byte_parity(value: int) -> None:
    from minecraft_bot.codec import Writer as PyWriter
    from minecraft_bot.codec import varlong as py_varlong
    from minecraft_bot_accel.codec import Writer as AcWriter
    from minecraft_bot_accel.codec import varlong as ac_varlong

    pw = PyWriter()
    py_varlong.write(value, pw)
    py_bytes = pw.bytes()

    aw = AcWriter()
    ac_varlong.write(value, aw)
    ac_bytes = aw.bytes()

    assert (
        py_bytes == ac_bytes
    ), f"varlong.write({value}) divergence: py={py_bytes.hex()} ac={ac_bytes.hex()}"


def test_framer_encode_parity() -> None:
    """Framer encodes a payload identically across backends (no compression)."""
    from minecraft_bot.framer import Framer as PyFramer
    from minecraft_bot_accel.framer import Framer as AcFramer

    payload = bytes(range(50))
    py_framed = PyFramer().encode(payload)
    ac_framed = AcFramer().encode(payload)
    assert (
        py_framed == ac_framed
    ), f"framer.encode divergence: py={py_framed.hex()} ac={ac_framed.hex()}"


def test_framer_decode_parity() -> None:
    """Encode in Python framer, decode in accel framer: same payload."""
    from minecraft_bot.framer import Framer as PyFramer
    from minecraft_bot_accel.framer import Framer as AcFramer

    payload = bytes(range(80))
    py_framed = PyFramer().encode(payload)

    af = AcFramer()
    af.feed(py_framed)
    extracted = af.try_extract()
    assert extracted == payload
