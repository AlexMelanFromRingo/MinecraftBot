"""NBT codec tests — all 13 tag types, round-trip, edge cases."""

from __future__ import annotations

import pytest

from minecraft_bot.codec import Reader, Writer, nbt
from minecraft_bot.errors import MalformedNbt, ValueOutOfRange

from ._fixtures import codec_fixtures


def test_none_round_trip() -> None:
    """None NBT (no tag) = single TAG_End byte."""
    w = Writer(); nbt.write(None, w)
    assert w.bytes() == b"\x00"
    assert nbt.read(Reader(w.bytes())) is None


def test_empty_compound_round_trip() -> None:
    empty = nbt.NbtCompound()
    w = Writer(); nbt.write(empty, w)
    assert nbt.read(Reader(w.bytes())) == empty


def test_all_primitive_tag_types() -> None:
    """Round-trip a Compound containing every primitive tag type."""
    import struct
    f32_exact = struct.unpack(">f", struct.pack(">f", 3.14))[0]
    compound = nbt.NbtCompound(items=(
        ("byte", nbt.NbtByte(-5)),
        ("short", nbt.NbtShort(1234)),
        ("int", nbt.NbtInt(-2_000_000_000)),
        ("long", nbt.NbtLong(9_223_372_036_854_775_000)),
        ("float", nbt.NbtFloat(f32_exact)),
        ("double", nbt.NbtDouble(2.718281828)),
        ("byte_array", nbt.NbtByteArray(b"\x00\x01\xff\x7f\x80")),
        ("string", nbt.NbtString("hello")),
        ("int_array", nbt.NbtIntArray((1, 2, 3))),
        ("long_array", nbt.NbtLongArray((100, 200, -1))),
    ))
    w = Writer(); nbt.write(compound, w)
    assert nbt.read(Reader(w.bytes())) == compound


def test_list_homogeneous() -> None:
    lst = nbt.NbtList(element_type=nbt.TAG_INT, items=(
        nbt.NbtInt(1), nbt.NbtInt(2), nbt.NbtInt(3),
    ))
    compound = nbt.NbtCompound(items=(("list", lst),))
    w = Writer(); nbt.write(compound, w)
    out = nbt.read(Reader(w.bytes()))
    assert out == compound


def test_empty_list() -> None:
    """Empty list with element_type=TAG_END."""
    empty_list = nbt.NbtList(element_type=nbt.TAG_END, items=())
    compound = nbt.NbtCompound(items=(("empty", empty_list),))
    w = Writer(); nbt.write(compound, w)
    assert nbt.read(Reader(w.bytes())) == compound


def test_list_heterogeneous_raises() -> None:
    bad = nbt.NbtList(element_type=nbt.TAG_INT, items=(
        nbt.NbtInt(1),
        nbt.NbtString("not an int"),  # different type
    ))
    with pytest.raises(ValueOutOfRange):
        nbt.write(bad, Writer())


def test_nested_compound() -> None:
    inner = nbt.NbtCompound(items=(("inner_key", nbt.NbtString("inner_value")),))
    outer = nbt.NbtCompound(items=(("nested", inner),))
    w = Writer(); nbt.write(outer, w)
    assert nbt.read(Reader(w.bytes())) == outer


def test_byte_overflow_in_constructor() -> None:
    with pytest.raises(ValueOutOfRange):
        nbt.NbtByte(128)
    with pytest.raises(ValueOutOfRange):
        nbt.NbtByte(-129)


def test_unknown_tag_id_raises() -> None:
    """Tag id 99 is not defined; decoding it should raise MalformedNbt."""
    bad = bytes([99])  # invalid tag type as root
    with pytest.raises(MalformedNbt):
        nbt.read(Reader(bad))


def test_empty_compound_in_compound() -> None:
    """A compound containing an empty compound."""
    inner = nbt.NbtCompound()
    outer = nbt.NbtCompound(items=(("empty_child", inner),))
    w = Writer(); nbt.write(outer, w)
    assert nbt.read(Reader(w.bytes())) == outer


@pytest.mark.parametrize("fx", codec_fixtures("nbt"), ids=lambda fx: fx["kind"])
def test_nbt_golden(fx: dict) -> None:
    """The hex fixture decodes to *something* without raising; we don't
    pin the value form because Python repr of NBT structures is verbose,
    but the fixtures themselves were produced by encode() so a re-encode
    must reproduce the bytes."""
    raw = bytes.fromhex(fx["hex"])
    decoded = nbt.read(Reader(raw))
    w = Writer(); nbt.write(decoded, w)
    assert w.bytes() == raw
