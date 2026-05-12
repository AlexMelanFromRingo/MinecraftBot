"""Entity metadata stream codec tests (T023)."""

from __future__ import annotations

import struct
import uuid as _uuid

from minecraft_bot.codec import Reader, Writer
from minecraft_bot.codec import metadata as md


def _round_trip(values: dict[int, tuple[int, object]]) -> dict[int, tuple[int, object]]:
    w = Writer()
    md.write(values, w)
    return md.read(Reader(w.bytes()))


def test_empty_stream_terminator_only() -> None:
    w = Writer()
    md.write({}, w)
    assert w.bytes() == bytes([md.TERMINATOR])
    assert md.read(Reader(w.bytes())) == {}


def test_byte_value() -> None:
    out = _round_trip({0: (md.T_BYTE, -5)})
    assert out[0] == (md.T_BYTE, -5)


def test_varint_value() -> None:
    out = _round_trip({1: (md.T_VARINT, 12345)})
    assert out[1] == (md.T_VARINT, 12345)


def test_float_value() -> None:
    out = _round_trip({2: (md.T_FLOAT, 1.5)})
    assert out[2][1] == 1.5


def test_string_value() -> None:
    out = _round_trip({3: (md.T_STRING, "hello world")})
    assert out[3] == (md.T_STRING, "hello world")


def test_bool_value() -> None:
    out = _round_trip({4: (md.T_BOOL, True)})
    assert out[4] == (md.T_BOOL, True)


def test_rotation_triple() -> None:
    out = _round_trip({5: (md.T_ROTATION, (0.1, 0.2, 0.3))})
    assert out[5][0] == md.T_ROTATION
    for a, b in zip(out[5][1], (0.1, 0.2, 0.3)):
        assert abs(a - b) < 1e-5


def test_optuuid_present_and_absent() -> None:
    u = _uuid.uuid4()
    out_present = _round_trip({6: (md.T_OPTUUID, u)})
    assert out_present[6][1] == u
    out_absent = _round_trip({7: (md.T_OPTUUID, None)})
    assert out_absent[7][1] is None


def test_optblockstate_zero_is_none() -> None:
    out = _round_trip({8: (md.T_OPTBLOCKSTATE, None)})
    assert out[8][1] is None
    out2 = _round_trip({9: (md.T_OPTBLOCKSTATE, 42)})
    assert out2[9][1] == 42


def test_pose_varint() -> None:
    out = _round_trip({10: (md.T_POSE, 3)})
    assert out[10] == (md.T_POSE, 3)


def test_optvarint_encoding_offset() -> None:
    """OptVarInt: 0 means None; non-None values are encoded as value+1."""
    out = _round_trip({11: (md.T_OPTVARINT, None)})
    assert out[11][1] is None
    out2 = _round_trip({12: (md.T_OPTVARINT, 7)})
    assert out2[12][1] == 7


def test_villager_data_triple() -> None:
    out = _round_trip({13: (md.T_VILLAGER_DATA, (1, 2, 3))})
    assert out[13] == (md.T_VILLAGER_DATA, (1, 2, 3))


def test_multi_entry_stream_preserves_order() -> None:
    inp = {
        0: (md.T_BYTE, 0x40),       # entity flags
        1: (md.T_VARINT, 300),      # air ticks
        7: (md.T_FLOAT, 20.0),      # health
        8: (md.T_VARINT, 0),
    }
    out = _round_trip(inp)
    assert out == inp


def test_round_trip_with_real_minecraft_byte_pattern() -> None:
    """A synthetic but realistic player metadata payload (flags + health)."""
    w = Writer()
    # Index 0 (entity flags): byte 0x10 (sprinting)
    w.write(bytes([0]))
    w.write(bytes([md.T_BYTE]))
    w.write(struct.pack(">b", 0x10))
    # Index 9 (health): float 17.5
    w.write(bytes([9]))
    w.write(bytes([md.T_FLOAT]))
    w.write(struct.pack(">f", 17.5))
    # Terminator
    w.write(bytes([md.TERMINATOR]))
    parsed = md.read(Reader(w.bytes()))
    assert parsed[0] == (md.T_BYTE, 0x10)
    assert parsed[9][0] == md.T_FLOAT
    assert abs(parsed[9][1] - 17.5) < 1e-5
