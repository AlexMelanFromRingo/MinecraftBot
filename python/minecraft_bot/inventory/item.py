"""ItemSlot: a typed wrapper around the wire-level SlotData (T053).

Encapsulates an inventory item along with NBT-derived properties so
the bot can answer ``slot.damage``, ``slot.enchantments``, etc.
without re-parsing NBT every time.

Item-name resolution uses ``protocol-data/v763/item_table.json``
(generated from PrismarineJS ``items.json``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from minecraft_bot.codec import nbt as _nbt
from minecraft_bot.codec.slot import SlotData

# --- item-name table (loaded once at import time) -------------------------

_REPO = Path(__file__).resolve().parents[3]
_ITEM_TABLE_PATH = _REPO / "protocol-data" / "v763" / "item_table.json"
with _ITEM_TABLE_PATH.open("r", encoding="utf-8") as _fh:
    _ITEMS: dict[str, dict] = json.load(_fh)
_BY_ID: dict[int, dict] = {int(k): v for k, v in _ITEMS.items()}
_BY_NAME: dict[str, int] = {v["name"]: int(k) for k, v in _ITEMS.items()}


def item_name(item_id: int) -> str | None:
    """``42`` → ``'minecraft:iron_block'``, or ``None`` if unknown."""
    entry = _BY_ID.get(item_id)
    return entry["name"] if entry else None


def item_id(name: str) -> int | None:
    """``'iron_block'`` or ``'minecraft:iron_block'`` → numeric id."""
    if ":" not in name:
        name = "minecraft:" + name
    return _BY_NAME.get(name)


# --- Enchantment record ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class Enchantment:
    """One enchantment on an item."""

    id: str          # registry id, e.g. "minecraft:sharpness"
    level: int


def _nbt_get(comp: _nbt.NbtCompound | None, name: str):
    """Helper to read a tag from a compound (or None if absent)."""
    if comp is None:
        return None
    return comp.get(name)


def _nbt_value(tag):
    """Extract the underlying Python value from an Nbt* tag."""
    if tag is None:
        return None
    return getattr(tag, "value", None)


# --- ItemSlot -----------------------------------------------------------


@dataclass(slots=True)
class ItemSlot:
    """A populated inventory slot with typed access to common NBT
    fields. ``None`` is used elsewhere for empty slots — *this class
    never represents an empty slot*.
    """

    item_id: int
    count: int
    tag: _nbt.NbtCompound | None = None

    # --- naming --------------------------------------------------------

    @property
    def name(self) -> str | None:
        return item_name(self.item_id)

    @property
    def stack_size(self) -> int:
        entry = _BY_ID.get(self.item_id)
        return entry["stack_size"] if entry else 64

    # --- NBT-derived properties ---------------------------------------

    @property
    def damage(self) -> int:
        """Durability damage. 0 = pristine."""
        v = _nbt_value(_nbt_get(self.tag, "Damage"))
        return int(v) if v is not None else 0

    @property
    def is_unbreakable(self) -> bool:
        v = _nbt_value(_nbt_get(self.tag, "Unbreakable"))
        return bool(v) if v is not None else False

    @property
    def custom_model_data(self) -> int | None:
        v = _nbt_value(_nbt_get(self.tag, "CustomModelData"))
        return int(v) if v is not None else None

    @property
    def display_name(self) -> str | None:
        """Returns the raw JSON chat component string from
        ``display.Name``, or ``None`` if no custom name is set."""
        display = _nbt_get(self.tag, "display")
        if not isinstance(display, _nbt.NbtCompound):
            return None
        return _nbt_value(_nbt_get(display, "Name"))

    @property
    def enchantments(self) -> list[Enchantment]:
        """Parsed list of enchantments (empty list if none)."""
        # On normal items, enchantments live at "Enchantments"; on
        # enchanted books they live at "StoredEnchantments".
        raw = _nbt_get(self.tag, "Enchantments") or _nbt_get(self.tag, "StoredEnchantments")
        if not isinstance(raw, _nbt.NbtList):
            return []
        out: list[Enchantment] = []
        for ench in raw.items:
            if not isinstance(ench, _nbt.NbtCompound):
                continue
            ench_id = _nbt_value(_nbt_get(ench, "id"))
            ench_lvl = _nbt_value(_nbt_get(ench, "lvl"))
            if ench_id is None or ench_lvl is None:
                continue
            out.append(Enchantment(id=str(ench_id), level=int(ench_lvl)))
        return out

    # --- conversions ---------------------------------------------------

    @classmethod
    def from_slot_data(cls, slot: SlotData | None) -> ItemSlot | None:
        """Build an ItemSlot from a wire-level SlotData (or None)."""
        if slot is None:
            return None
        return cls(item_id=slot.item_id, count=slot.count, tag=slot.tag)

    def to_slot_data(self) -> SlotData:
        return SlotData(item_id=self.item_id, count=self.count, tag=self.tag)


__all__ = [
    "Enchantment",
    "ItemSlot",
    "item_id",
    "item_name",
]
