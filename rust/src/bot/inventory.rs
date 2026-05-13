//! Inventory state machine + Bot methods. Mirrors
//! `python/minecraft_bot/inventory/tracker.py` (state) and
//! `bot.py:822-965` (methods).
//!
//! 004 Group F (T046..T054).
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

    /// Read-only access to player slot at `index` (`0..46`). Returns
    /// `None` for out-of-range index or empty slot.
    pub fn get_player_slot(&self, index: usize) -> Option<&ItemSlot> {
        self.player_slots.get(index).and_then(|s| s.as_ref())
    }
}

// ---------------------------------------------------------------------------
// Bot methods (FR-022..FR-032, FR-024a).

use super::Bot;
use crate::errors::ProtocolError;
use crate::protocol::v763::packets::play::serverbound::held_item_slot::HeldItemSlot;
use crate::protocol::v763::packets::play::serverbound::window_click::WindowClick;

/// WindowClick mode constants (Mojang protocol).
const MODE_NORMAL_CLICK: i32 = 0;
const MODE_SHIFT_CLICK: i32 = 1;
const MODE_DROP: i32 = 4;
const MODE_SWAP_OFFHAND: i32 = 6;

/// Armor slot indices on the player inventory window.
pub fn armor_slot_index(name: &str) -> Option<usize> {
    match name {
        "head" | "helmet" => Some(SLOT_ARMOR_HEAD),
        "chest" | "chestplate" => Some(SLOT_ARMOR_CHEST),
        "legs" | "leggings" => Some(SLOT_ARMOR_LEGS),
        "feet" | "boots" => Some(SLOT_ARMOR_FEET),
        _ => None,
    }
}

impl Bot {
    /// Read currently-held hotbar slot's item. Q5 invariant: reads
    /// only `player_slots`.
    pub async fn held_item(&self) -> Option<ItemSlot> {
        let inv = self.inventory.lock().await;
        let slot = self.state.lock().await.held_slot as usize;
        inv.get_player_slot(SLOT_HOTBAR_FIRST + slot).cloned()
    }

    /// First player slot index whose item name matches `name`.
    /// Reads `player_slots` only (Q5).
    pub async fn find_item(&self, name: &str) -> Option<usize> {
        let inv = self.inventory.lock().await;
        for (i, s) in inv.player_slots.iter().enumerate() {
            if let Some(item) = s {
                if item.name() == name {
                    return Some(i);
                }
            }
        }
        None
    }

    /// Total stack count for items named `name`. `player_slots` only.
    pub async fn count_item(&self, name: &str) -> u32 {
        let inv = self.inventory.lock().await;
        inv.player_slots
            .iter()
            .filter_map(|s| s.as_ref())
            .filter(|item| item.name() == name)
            .map(|item| item.count as u32)
            .sum()
    }

    /// Iterate all visible slots — player_slots + container_slots.
    /// Returns owned snapshots to avoid lifetime issues with the
    /// async lock.
    pub async fn iter_accessible_slots(&self) -> Vec<(usize, Option<ItemSlot>)> {
        let inv = self.inventory.lock().await;
        let mut out: Vec<(usize, Option<ItemSlot>)> =
            inv.player_slots.iter().cloned().enumerate().collect();
        let base = out.len();
        for (i, s) in inv.container_slots.iter().cloned().enumerate() {
            out.push((base + i, s));
        }
        out
    }

    /// Switch the active hotbar slot (0..8). Sends `HeldItemSlot`
    /// and updates local state optimistically.
    pub async fn select_slot(&self, hotbar_index: u8) -> Result<(), ProtocolError> {
        if hotbar_index > 8 {
            return Err(ProtocolError::DecodeError(format!(
                "hotbar_index must be 0..8, got {hotbar_index}"
            )));
        }
        self.connection
            .send(&HeldItemSlot {
                slot_id: hotbar_index as i16,
            })
            .await?;
        self.state.lock().await.held_slot = hotbar_index;
        Ok(())
    }

    /// Drop the currently-held item (or stack). Mirrors Python:
    /// uses WindowClick mode=4 instead of BlockDig because Paper
    /// silently ignores BlockDig stack-drops from non-vanilla clients.
    pub async fn drop_item(&self, drop_stack: bool) -> Result<(), ProtocolError> {
        let _guard = self.inventory.lock().await; // serialise inventory writes
        let held_slot = self.state.lock().await.held_slot as i16;
        let state_id = _guard.state_id;
        let slot_index = (SLOT_HOTBAR_FIRST as i16) + held_slot;
        self.connection
            .send(&WindowClick {
                window_id: 0,
                state_id,
                slot_index,
                mouse_button: if drop_stack { 1 } else { 0 },
                mode: MODE_DROP,
                changed_slots: Vec::new(),
                carried_item: None,
            })
            .await
    }

    /// Send a window-click packet. `mode_str` is one of
    /// `"left"`, `"right"`, `"shift_left"`, `"shift_right"`,
    /// `"swap_offhand"`. `window_id` defaults to current open window.
    pub async fn click_slot(
        &self,
        slot_index: i16,
        mode_str: &str,
        button: i8,
        window_id: Option<u8>,
    ) -> Result<(), ProtocolError> {
        let inv = self.inventory.lock().await;
        let wid = window_id.unwrap_or(inv.window_id);
        let state_id = inv.state_id;
        let (mode, btn) = match mode_str {
            "left" => (MODE_NORMAL_CLICK, button),
            "right" => (MODE_NORMAL_CLICK, 1),
            "shift_left" => (MODE_SHIFT_CLICK, 0),
            "shift_right" => (MODE_SHIFT_CLICK, 1),
            "swap_offhand" => (MODE_SWAP_OFFHAND, 40),
            other => {
                return Err(ProtocolError::DecodeError(format!(
                    "unknown click mode: {other}"
                )));
            }
        };
        drop(inv);
        self.connection
            .send(&WindowClick {
                window_id: wid,
                state_id,
                slot_index,
                mouse_button: btn,
                mode,
                changed_slots: Vec::new(),
                carried_item: None,
            })
            .await
    }

    /// Move the entire stack at `src` to `dst` via pick-up + put-down
    /// (two left-clicks). Matches Python `bot.py:move_item`.
    pub async fn move_item(
        &self,
        src: i16,
        dst: i16,
        window_id: Option<u8>,
    ) -> Result<(), ProtocolError> {
        self.click_slot(src, "left", 0, window_id).await?;
        tokio::time::sleep(std::time::Duration::from_millis(50)).await;
        self.click_slot(dst, "left", 0, window_id).await
    }

    /// Shift-click — auto-shuffle stack between player and container.
    pub async fn quick_move(&self, slot: i16, window_id: Option<u8>) -> Result<(), ProtocolError> {
        self.click_slot(slot, "shift_left", 0, window_id).await
    }

    /// Move an armor piece from `src_slot` into the right armor slot.
    pub async fn equip_armor(&self, armor_slot: &str, src_slot: i16) -> Result<(), ProtocolError> {
        let dst = armor_slot_index(armor_slot).ok_or_else(|| {
            ProtocolError::DecodeError(format!("unknown armor slot: {armor_slot}"))
        })?;
        self.move_item(src_slot, dst as i16, Some(0)).await
    }

    /// Move armor from its slot back to `dst_slot` in the main inventory.
    pub async fn unequip_armor(
        &self,
        armor_slot: &str,
        dst_slot: i16,
    ) -> Result<(), ProtocolError> {
        let src = armor_slot_index(armor_slot).ok_or_else(|| {
            ProtocolError::DecodeError(format!("unknown armor slot: {armor_slot}"))
        })?;
        self.move_item(src as i16, dst_slot, Some(0)).await
    }

    /// Swap the item at `src_slot` with the off-hand via F-key.
    pub async fn swap_to_offhand(&self, src_slot: i16) -> Result<(), ProtocolError> {
        self.click_slot(src_slot, "swap_offhand", 40, Some(0)).await
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
