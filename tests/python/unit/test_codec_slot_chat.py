"""Slot and ChatComponent codec tests."""

from __future__ import annotations

import pytest

from minecraft_bot.codec import Reader, Writer, chat_component, nbt, slot
from minecraft_bot.errors import ValueOutOfRange

from ._fixtures import codec_fixtures

# --- slot ------------------------------------------------------------------


def test_empty_slot() -> None:
    w = Writer(); slot.write(None, w)
    assert w.bytes() == b"\x00"
    assert slot.read(Reader(b"\x00")) is None


def test_slot_no_nbt() -> None:
    s = slot.SlotData(item_id=1, count=64, tag=None)
    w = Writer(); slot.write(s, w)
    assert slot.read(Reader(w.bytes())) == s


def test_slot_with_nbt() -> None:
    tag = nbt.NbtCompound(items=(
        ("Damage", nbt.NbtInt(0)),
        ("Enchantments", nbt.NbtList(element_type=nbt.TAG_COMPOUND, items=(
            nbt.NbtCompound(items=(
                ("id", nbt.NbtString("minecraft:sharpness")),
                ("lvl", nbt.NbtShort(5)),
            )),
        ))),
    ))
    s = slot.SlotData(item_id=276, count=1, tag=tag)
    w = Writer(); slot.write(s, w)
    assert slot.read(Reader(w.bytes())) == s


def test_slot_count_out_of_range() -> None:
    with pytest.raises(ValueOutOfRange):
        slot.write(slot.SlotData(item_id=1, count=128, tag=None), Writer())
    with pytest.raises(ValueOutOfRange):
        slot.write(slot.SlotData(item_id=1, count=-129, tag=None), Writer())


def test_slot_invalid_present_byte() -> None:
    """Anything other than 0x00/0x01 in the present byte is malformed."""
    with pytest.raises(ValueOutOfRange):
        slot.read(Reader(b"\x02\x00\x00\x00"))


@pytest.mark.parametrize("fx", codec_fixtures("slot"), ids=lambda fx: fx["kind"])
def test_slot_golden(fx: dict) -> None:
    """Each golden hex re-encodes to itself after a decode round-trip."""
    raw = bytes.fromhex(fx["hex"])
    decoded = slot.read(Reader(raw))
    w = Writer(); slot.write(decoded, w)
    assert w.bytes() == raw


# --- chat_component --------------------------------------------------------


@pytest.mark.parametrize("fx", codec_fixtures("chat_component"), ids=lambda fx: fx["value"][:30])
def test_chat_component_golden(fx: dict) -> None:
    expected = bytes.fromhex(fx["hex"])
    w = Writer(); chat_component.write(fx["value"], w)
    assert w.bytes() == expected
    assert chat_component.read(Reader(expected)) == fx["value"]


def test_chat_component_oversized() -> None:
    too_long = "x" * (chat_component.MAX_LENGTH + 1)
    with pytest.raises(ValueOutOfRange):
        chat_component.write(too_long, Writer())
