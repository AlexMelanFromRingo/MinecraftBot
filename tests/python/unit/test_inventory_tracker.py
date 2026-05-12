"""InventoryTracker state-evolution tests (T062)."""

from __future__ import annotations

from minecraft_bot.codec.slot import SlotData
from minecraft_bot.inventory.item import item_id
from minecraft_bot.inventory.tracker import (
    InventoryTracker, PLAYER_INVENTORY_SIZE,
    SLOT_HOTBAR_FIRST, SLOT_OFFHAND,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.close_window import (
    CloseWindow,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.open_window import (
    OpenWindow,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.set_slot import (
    SetSlot,
)
from minecraft_bot.protocol.v763.packets.play.clientbound.window_items import (
    WindowItems,
)


def _slot(name: str, count: int = 1) -> SlotData:
    return SlotData(item_id=item_id(name), count=count, tag=None)


def test_initial_state_is_empty() -> None:
    inv = InventoryTracker()
    assert all(s is None for s in inv.player_slots)
    assert inv.cursor is None
    assert inv.state_id == 0
    assert inv.container_window_id is None


def test_window_items_for_player_populates_slots() -> None:
    inv = InventoryTracker()
    items = [None] * PLAYER_INVENTORY_SIZE
    items[SLOT_HOTBAR_FIRST] = _slot("diamond_sword", 1)
    items[SLOT_HOTBAR_FIRST + 1] = _slot("stone", 64)
    inv.on_window_items(WindowItems(
        window_id=0, state_id=5, items=tuple(items), carried_item=None,
    ))
    assert inv.state_id == 5
    slot0 = inv.player_slots[SLOT_HOTBAR_FIRST]
    assert slot0 is not None and slot0.name == "minecraft:diamond_sword"
    slot1 = inv.player_slots[SLOT_HOTBAR_FIRST + 1]
    assert slot1 is not None and slot1.count == 64


def test_set_slot_single_update() -> None:
    inv = InventoryTracker()
    inv.on_set_slot(SetSlot(
        window_id=0, state_id=1, slot_index=SLOT_OFFHAND,
        item=_slot("shield"),
    ))
    assert inv.player_slots[SLOT_OFFHAND].name == "minecraft:shield"


def test_set_slot_cursor() -> None:
    inv = InventoryTracker()
    inv.on_set_slot(SetSlot(
        window_id=-1, state_id=2, slot_index=-1,
        item=_slot("bread", 16),
    ))
    assert inv.cursor is not None
    assert inv.cursor.name == "minecraft:bread"
    assert inv.cursor.count == 16


def test_find_item_and_count_item() -> None:
    inv = InventoryTracker()
    items = [None] * PLAYER_INVENTORY_SIZE
    items[10] = _slot("apple", 5)
    items[12] = _slot("apple", 3)
    items[20] = _slot("bread", 2)
    inv.on_window_items(WindowItems(
        window_id=0, state_id=1, items=tuple(items), carried_item=None,
    ))
    assert inv.find_item("apple") == 10
    assert inv.count_item("apple") == 8
    assert inv.count_item("bread") == 2
    assert inv.count_item("diamond") == 0
    assert inv.find_item("diamond") is None


def test_open_window_starts_container() -> None:
    inv = InventoryTracker()
    inv.on_open_window(OpenWindow(
        window_id=1, inventory_type=2, window_title='{"text":"Chest"}',
    ))
    assert inv.container_window_id == 1
    assert inv.container_type == 2


def test_container_window_items_populates_container_slots() -> None:
    inv = InventoryTracker()
    inv.on_open_window(OpenWindow(
        window_id=1, inventory_type=2, window_title='{"text":"Chest"}',
    ))
    items = [None, _slot("diamond", 64), None, _slot("emerald", 5)] + [None] * 50
    inv.on_window_items(WindowItems(
        window_id=1, state_id=10, items=tuple(items), carried_item=None,
    ))
    assert inv.container_slots[1].name == "minecraft:diamond"
    assert inv.container_slots[3].count == 5
    assert inv.find_in_container("diamond") == 1


def test_close_window_clears_container_state() -> None:
    inv = InventoryTracker()
    inv.on_open_window(OpenWindow(
        window_id=1, inventory_type=2, window_title='{"text":"Chest"}',
    ))
    inv.on_close_window(CloseWindow(window_id=1))
    assert inv.container_window_id is None
    assert inv.container_slots == []


def test_close_window_with_wrong_id_is_silent_noop() -> None:
    inv = InventoryTracker()
    inv.on_open_window(OpenWindow(
        window_id=1, inventory_type=2, window_title='',
    ))
    inv.on_close_window(CloseWindow(window_id=99))
    assert inv.container_window_id == 1


def test_hotbar_and_armor_views() -> None:
    inv = InventoryTracker()
    items = [None] * PLAYER_INVENTORY_SIZE
    items[5] = _slot("iron_helmet")
    items[SLOT_HOTBAR_FIRST] = _slot("stick", 1)
    items[SLOT_HOTBAR_FIRST + 4] = _slot("apple", 64)
    inv.on_window_items(WindowItems(
        window_id=0, state_id=1, items=tuple(items), carried_item=None,
    ))
    armor = inv.armor_items()
    assert armor["head"].name == "minecraft:iron_helmet"
    hotbar = inv.hotbar_items()
    assert len(hotbar) == 9
    assert hotbar[0].name == "minecraft:stick"
    assert hotbar[4].name == "minecraft:apple"
