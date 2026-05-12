"""InventoryTracker (T055-T056).

Mirrors the server's view of the bot's inventory + any currently open
container. Subscribed clientbound packets:

- ``set_slot``     — single slot update
- ``window_items`` — bulk refresh (sent on inventory open + state desync)
- ``open_window``  — container UI opened
- ``close_window`` — container UI closed (server-initiated)

Slot index layout (the player's own ``window_id == 0``):

- 0..4    crafting + result (0 = result, 1..4 = 2×2 grid)
- 5..8    armor (head/chest/legs/feet)
- 9..35   main inventory (3 rows × 9 columns, top to bottom)
- 36..44  hotbar (slot 36 = key 1, 44 = key 9)
- 45      off-hand

When a container is open (``window_id > 0``), slots 0..n-1 are the
container's slots and slots n..n+35 are the player's main inventory +
hotbar.
"""

from __future__ import annotations

from typing import Iterable, Iterator, Optional

from minecraft_bot.inventory.item import ItemSlot, item_id

PLAYER_INVENTORY_SIZE = 46

# Indices into the player's window_id == 0 view.
SLOT_CRAFT_RESULT = 0
SLOT_CRAFT_2x2 = range(1, 5)
SLOT_ARMOR_HEAD = 5
SLOT_ARMOR_CHEST = 6
SLOT_ARMOR_LEGS = 7
SLOT_ARMOR_FEET = 8
SLOT_MAIN_FIRST = 9        # 9..35 main 3×9
SLOT_MAIN_LAST = 35
SLOT_HOTBAR_FIRST = 36     # 36..44 hotbar
SLOT_HOTBAR_LAST = 44
SLOT_OFFHAND = 45


class InventoryTracker:
    """Per-bot inventory state, source-of-truth for inventory queries."""

    __slots__ = (
        "player_slots", "cursor", "state_id",
        "container_window_id", "container_type", "container_title",
        "container_slots",
    )

    def __init__(self) -> None:
        self.player_slots: list[Optional[ItemSlot]] = [None] * PLAYER_INVENTORY_SIZE
        self.cursor: Optional[ItemSlot] = None
        self.state_id: int = 0
        # Container state (None when no container is open).
        self.container_window_id: Optional[int] = None
        self.container_type: Optional[int] = None
        self.container_title: Optional[str] = None
        self.container_slots: list[Optional[ItemSlot]] = []

    # --- packet handlers ----------------------------------------------

    def on_window_items(self, p) -> None:
        """Bulk refresh. Window 0 = player; otherwise it's the open container."""
        slots = [ItemSlot.from_slot_data(s) for s in p.items]
        self.state_id = p.state_id
        self.cursor = ItemSlot.from_slot_data(p.carried_item)
        if p.window_id == 0:
            # Pad or truncate to PLAYER_INVENTORY_SIZE.
            for i, s in enumerate(slots[:PLAYER_INVENTORY_SIZE]):
                self.player_slots[i] = s
        else:
            self.container_window_id = p.window_id
            # First N slots are the container's own slots; remaining 36
            # are the player's main + hotbar (mirrored from player_slots).
            self.container_slots = list(slots)

    def on_set_slot(self, p) -> None:
        """Single-slot update. ``window_id == -1`` is the cursor;
        ``window_id == 0`` is the player; otherwise container."""
        self.state_id = p.state_id
        if p.window_id == -1:
            self.cursor = ItemSlot.from_slot_data(p.item)
            return
        if p.window_id == 0:
            if 0 <= p.slot_index < PLAYER_INVENTORY_SIZE:
                self.player_slots[p.slot_index] = ItemSlot.from_slot_data(p.item)
            return
        # Container slot.
        if p.window_id == self.container_window_id:
            if 0 <= p.slot_index < len(self.container_slots):
                self.container_slots[p.slot_index] = ItemSlot.from_slot_data(p.item)

    def on_open_window(self, p) -> None:
        self.container_window_id = p.window_id
        self.container_type = p.inventory_type
        self.container_title = p.window_title
        self.container_slots = []   # will be filled by window_items

    def on_close_window(self, p) -> None:
        """Server-initiated close — clear container state."""
        if p.window_id == self.container_window_id:
            self.container_window_id = None
            self.container_type = None
            self.container_title = None
            self.container_slots = []

    def on_held_item_slot(self, p) -> None:
        # The serverbound held_item_slot updates the bot's selected hotbar
        # index — this is exposed on the Bot level, not here. We just
        # leave a hook in case future code wants it.
        pass

    # --- public query API (FR-060..FR-070) ----------------------------

    def items(self) -> list[Optional[ItemSlot]]:
        """The entire player inventory snapshot (length 46)."""
        return list(self.player_slots)

    def hotbar_items(self) -> list[Optional[ItemSlot]]:
        """Just the 9 hotbar slots (key 1 = index 0)."""
        return self.player_slots[SLOT_HOTBAR_FIRST:SLOT_HOTBAR_LAST + 1]

    def armor_items(self) -> dict[str, Optional[ItemSlot]]:
        return {
            "head": self.player_slots[SLOT_ARMOR_HEAD],
            "chest": self.player_slots[SLOT_ARMOR_CHEST],
            "legs": self.player_slots[SLOT_ARMOR_LEGS],
            "feet": self.player_slots[SLOT_ARMOR_FEET],
        }

    def offhand_item(self) -> Optional[ItemSlot]:
        return self.player_slots[SLOT_OFFHAND]

    def container_items(self) -> list[Optional[ItemSlot]]:
        return list(self.container_slots)

    def find_item(self, name: str) -> Optional[int]:
        """Return the first slot index where the named item appears, or None."""
        target = item_id(name)
        if target is None:
            return None
        for idx, slot in enumerate(self.player_slots):
            if slot is not None and slot.item_id == target:
                return idx
        return None

    def count_item(self, name: str) -> int:
        """Total count of the named item across all 46 slots."""
        target = item_id(name)
        if target is None:
            return 0
        return sum(
            slot.count for slot in self.player_slots
            if slot is not None and slot.item_id == target
        )

    def find_in_container(self, name: str) -> Optional[int]:
        target = item_id(name)
        if target is None:
            return None
        for idx, slot in enumerate(self.container_slots):
            if slot is not None and slot.item_id == target:
                return idx
        return None


__all__ = [
    "InventoryTracker", "PLAYER_INVENTORY_SIZE",
    "SLOT_CRAFT_RESULT", "SLOT_ARMOR_HEAD", "SLOT_ARMOR_CHEST",
    "SLOT_ARMOR_LEGS", "SLOT_ARMOR_FEET",
    "SLOT_MAIN_FIRST", "SLOT_MAIN_LAST",
    "SLOT_HOTBAR_FIRST", "SLOT_HOTBAR_LAST", "SLOT_OFFHAND",
]
