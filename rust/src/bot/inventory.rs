//! Inventory state machine + Bot methods. Mirrors
//! `python/minecraft_bot/inventory/tracker.py`.
//!
//! Spec Q5 invariant: `player_slots` is persistent (46 slots —
//! crafting result 0, crafting grid 1..4, armor 5..8, main 9..35,
//! hotbar 36..44, offhand 45). `container_slots` is transient and
//! populated only while a container window is open. `held_item`,
//! `find_item`, `count_item` MUST read only `player_slots`.
//! `iter_accessible_slots` is the *only* API that exposes the
//! merged view and is always derived, never canonical.
//!
//! 004 — T020 (state machine + unit tests). Bot methods land in
//! Phase 3 Group F.

#![allow(dead_code)]

use crate::inventory::ItemSlot;

/// Slot layout constants (matches
/// `python/minecraft_bot/inventory/tracker.py`).
pub const PLAYER_INVENTORY_SIZE: usize = 46;
pub const SLOT_ARMOR_HEAD: usize = 5;
pub const SLOT_ARMOR_CHEST: usize = 6;
pub const SLOT_ARMOR_LEGS: usize = 7;
pub const SLOT_ARMOR_FEET: usize = 8;
pub const SLOT_HOTBAR_FIRST: usize = 36;
pub const SLOT_HOTBAR_LAST: usize = 44;
pub const SLOT_OFFHAND: usize = 45;

/// Dual-list inventory state per spec Q5.
#[derive(Debug, Default)]
pub struct InventoryState {
    /// Persistent 46-slot player inventory.
    pub player_slots: Vec<Option<ItemSlot>>,
    /// Transient container slots — empty when no container window is
    /// open. Populated by `WindowItems` after an `OpenScreen`.
    pub container_slots: Vec<Option<ItemSlot>>,
    /// Cursor slot (held item between clicks).
    pub cursor: Option<ItemSlot>,
    /// Current window id (0 = player inventory window).
    pub window_id: u8,
    /// Server-side window state-id (carried in clicks).
    pub state_id: i32,
}

impl InventoryState {
    /// Build an empty inventory with all 46 player slots None.
    pub fn new() -> Self {
        Self {
            player_slots: vec![None; PLAYER_INVENTORY_SIZE],
            container_slots: Vec::new(),
            cursor: None,
            window_id: 0,
            state_id: 0,
        }
    }

    /// Apply a `SetSlot` packet. `window_id == 0` -> player_slots;
    /// otherwise the slot index is interpreted relative to the
    /// currently-open window, with overflow into the player tail.
    pub fn apply_set_slot(
        &mut self,
        window_id: u8,
        slot_index: i16,
        item: Option<ItemSlot>,
    ) {
        if window_id == 0 || self.container_slots.is_empty() {
            if let Ok(idx) = usize::try_from(slot_index) {
                if idx < self.player_slots.len() {
                    self.player_slots[idx] = item;
                }
            }
            return;
        }
        let csize = self.container_slots.len();
        let slot_index = match usize::try_from(slot_index) {
            Ok(v) => v,
            Err(_) => return,
        };
        if slot_index < csize {
            self.container_slots[slot_index] = item;
            return;
        }
        // Server resends the player inventory tail after container
        // slots. Mojang puts main inventory (9..35) followed by
        // hotbar (36..44) into slots [csize, csize+27, csize+36).
        // We map back to player_slots[9..45].
        let player_idx = slot_index - csize + 9;
        if player_idx < self.player_slots.len() {
            self.player_slots[player_idx] = item;
        }
    }

    /// Apply a `WindowItems` packet. Rewrites the affected window
    /// wholesale.
    pub fn apply_window_items(&mut self, window_id: u8, items: Vec<Option<ItemSlot>>) {
        if window_id == 0 {
            // Resize defensively in case the server sends an unexpected
            // length; pad/truncate to PLAYER_INVENTORY_SIZE.
            self.player_slots.clear();
            self.player_slots
                .extend(items.into_iter().take(PLAYER_INVENTORY_SIZE));
            while self.player_slots.len() < PLAYER_INVENTORY_SIZE {
                self.player_slots.push(None);
            }
            return;
        }
        let csize = self.container_slots.len();
        if csize == 0 {
            // Window was opened but container_size hasn't been
            // recorded yet. Heuristic: items.len() == csize + 36
            // (main+hotbar tail). Solve csize from the assumption.
            // The dispatcher should call `apply_open_screen` first;
            // if it hasn't, fall back to treating everything as
            // container slots.
            self.container_slots = items;
            return;
        }
        let mut iter = items.into_iter();
        for slot in &mut self.container_slots {
            *slot = iter.next().flatten();
        }
        // Remaining items refill player slots 9..45 (main + hotbar).
        let mut player_idx = 9;
        for tail in iter {
            if player_idx >= self.player_slots.len() {
                break;
            }
            self.player_slots[player_idx] = tail;
            player_idx += 1;
        }
    }

    /// Apply an `OpenScreen` packet — allocate `container_slots` to
    /// the requested size. Idempotent for the same window_id.
    pub fn apply_open_screen(&mut self, window_id: u8, container_size: usize) {
        self.window_id = window_id;
        self.container_slots = vec![None; container_size];
    }

    /// Apply a `CloseWindow` packet — reset transient state.
    pub fn apply_close_window(&mut self) {
        self.window_id = 0;
        self.container_slots.clear();
        self.cursor = None;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn slot(id: u32, count: u8) -> Option<ItemSlot> {
        Some(ItemSlot::new(id, count, None))
    }

    #[test]
    fn new_inventory_is_empty() {
        let inv = InventoryState::new();
        assert_eq!(inv.player_slots.len(), PLAYER_INVENTORY_SIZE);
        assert!(inv.container_slots.is_empty());
        assert!(inv.cursor.is_none());
        assert_eq!(inv.window_id, 0);
    }

    #[test]
    fn set_slot_player_window() {
        let mut inv = InventoryState::new();
        inv.apply_set_slot(0, 36, slot(853, 1));  // bread into hotbar[0]
        assert_eq!(inv.player_slots[SLOT_HOTBAR_FIRST], slot(853, 1));
    }

    #[test]
    fn set_slot_container_window_in_range() {
        let mut inv = InventoryState::new();
        inv.apply_open_screen(7, 27);  // single chest
        inv.apply_set_slot(7, 5, slot(1, 64));  // stone into chest slot 5
        assert_eq!(inv.container_slots[5], slot(1, 64));
    }

    #[test]
    fn set_slot_container_window_overflow_into_player_tail() {
        let mut inv = InventoryState::new();
        inv.apply_open_screen(7, 27);
        // Slot 30 in chest window = chest_size(27) + offset 3 = player 12
        inv.apply_set_slot(7, 30, slot(1, 64));
        assert_eq!(inv.player_slots[12], slot(1, 64));
        // Container slot 5 should still be empty.
        assert!(inv.container_slots[5].is_none());
    }

    #[test]
    fn window_items_player_window() {
        let mut inv = InventoryState::new();
        let mut items = vec![None; PLAYER_INVENTORY_SIZE];
        items[36] = slot(853, 5);
        inv.apply_window_items(0, items);
        assert_eq!(inv.player_slots[36], slot(853, 5));
    }

    #[test]
    fn window_items_container_window() {
        let mut inv = InventoryState::new();
        inv.apply_open_screen(7, 27);
        let mut items = vec![None; 27 + 36];
        items[0] = slot(1, 64);  // chest first slot
        items[27] = slot(2, 1);  // first player main slot
        inv.apply_window_items(7, items);
        assert_eq!(inv.container_slots[0], slot(1, 64));
        assert_eq!(inv.player_slots[9], slot(2, 1));
    }

    #[test]
    fn open_screen_then_close() {
        let mut inv = InventoryState::new();
        inv.apply_open_screen(7, 27);
        assert_eq!(inv.window_id, 7);
        assert_eq!(inv.container_slots.len(), 27);
        inv.apply_close_window();
        assert_eq!(inv.window_id, 0);
        assert!(inv.container_slots.is_empty());
    }

    #[test]
    fn close_window_clears_cursor() {
        let mut inv = InventoryState::new();
        inv.cursor = slot(853, 1);
        inv.apply_close_window();
        assert!(inv.cursor.is_none());
    }

    #[test]
    fn open_screen_replaces_existing_container() {
        let mut inv = InventoryState::new();
        inv.apply_open_screen(7, 27);
        inv.apply_set_slot(7, 0, slot(1, 1));
        // Opening a different window resets container_slots.
        inv.apply_open_screen(9, 54);  // double chest
        assert_eq!(inv.container_slots.len(), 54);
        assert!(inv.container_slots[0].is_none());
    }
}
