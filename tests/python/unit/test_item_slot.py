"""ItemSlot + NBT helper tests (T054)."""

from __future__ import annotations

from minecraft_bot.codec import nbt as _nbt
from minecraft_bot.codec.slot import SlotData
from minecraft_bot.inventory.item import (
    Enchantment,
    ItemSlot,
    item_id,
    item_name,
)


def test_item_name_lookup() -> None:
    assert item_name(0) == "minecraft:air"
    assert item_name(item_id("iron_block")) == "minecraft:iron_block"
    assert item_name(99999) is None


def test_item_id_round_trip() -> None:
    iid = item_id("diamond_sword")
    assert iid is not None
    assert item_id("minecraft:diamond_sword") == iid


def test_itemslot_basics_without_tag() -> None:
    s = ItemSlot(item_id=item_id("apple"), count=3)
    assert s.name == "minecraft:apple"
    assert s.count == 3
    assert s.damage == 0
    assert s.enchantments == []
    assert s.display_name is None
    assert s.is_unbreakable is False


def test_damage_from_nbt() -> None:
    tag = _nbt.NbtCompound(items=(("Damage", _nbt.NbtInt(value=5)),))
    s = ItemSlot(item_id=item_id("diamond_pickaxe"), count=1, tag=tag)
    assert s.damage == 5


def test_unbreakable_flag() -> None:
    tag = _nbt.NbtCompound(items=(("Unbreakable", _nbt.NbtByte(value=1)),))
    s = ItemSlot(item_id=item_id("netherite_sword"), count=1, tag=tag)
    assert s.is_unbreakable


def test_enchantments_parsed() -> None:
    ench = _nbt.NbtCompound(items=(
        ("id", _nbt.NbtString(value="minecraft:sharpness")),
        ("lvl", _nbt.NbtShort(value=5)),
    ))
    tag = _nbt.NbtCompound(items=(
        ("Enchantments", _nbt.NbtList(element_type=10, items=(ench,))),
    ))
    s = ItemSlot(item_id=item_id("diamond_sword"), count=1, tag=tag)
    assert s.enchantments == [Enchantment(id="minecraft:sharpness", level=5)]


def test_stored_enchantments_for_enchanted_book() -> None:
    ench = _nbt.NbtCompound(items=(
        ("id", _nbt.NbtString(value="minecraft:fortune")),
        ("lvl", _nbt.NbtShort(value=3)),
    ))
    tag = _nbt.NbtCompound(items=(
        ("StoredEnchantments", _nbt.NbtList(element_type=10, items=(ench,))),
    ))
    s = ItemSlot(item_id=item_id("enchanted_book"), count=1, tag=tag)
    assert s.enchantments == [Enchantment(id="minecraft:fortune", level=3)]


def test_display_name_from_nbt() -> None:
    display = _nbt.NbtCompound(items=(
        ("Name", _nbt.NbtString(value='{"text":"My Sword","color":"red"}')),
    ))
    tag = _nbt.NbtCompound(items=(("display", display),))
    s = ItemSlot(item_id=item_id("diamond_sword"), count=1, tag=tag)
    assert s.display_name == '{"text":"My Sword","color":"red"}'


def test_custom_model_data() -> None:
    tag = _nbt.NbtCompound(items=(("CustomModelData", _nbt.NbtInt(value=12345)),))
    s = ItemSlot(item_id=item_id("stick"), count=1, tag=tag)
    assert s.custom_model_data == 12345


def test_stack_size_lookup() -> None:
    assert ItemSlot(item_id=item_id("cobblestone"), count=1).stack_size == 64
    # Eggs stack to 16 in vanilla
    egg = item_id("egg")
    if egg is not None:
        assert ItemSlot(item_id=egg, count=1).stack_size == 16


def test_from_slot_data_roundtrip() -> None:
    raw = SlotData(item_id=42, count=5, tag=None)
    s = ItemSlot.from_slot_data(raw)
    assert s is not None
    assert s.item_id == 42
    assert s.count == 5
    back = s.to_slot_data()
    assert back.item_id == 42
    assert back.count == 5


def test_from_slot_data_none_returns_none() -> None:
    assert ItemSlot.from_slot_data(None) is None
