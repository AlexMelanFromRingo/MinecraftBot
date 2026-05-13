//! `ItemSlot` value type — one Minecraft item-in-slot. Mirrors
//! `python/minecraft_bot/inventory/item.py::ItemSlot`.
//!
//! 004 — fields wired by T019; helper methods (`name`, `from_slot_data`)
//! land with T019 once the items.json loader is in.

#![allow(dead_code)]

/// One item stack in an inventory slot.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ItemSlot {
    /// Numeric item id from `protocol-data/v763/items.json`.
    pub item_id: u32,
    /// Stack count.
    pub count: u8,
    /// Raw NBT bytes (decoded on demand).
    pub nbt: Option<Vec<u8>>,
}

impl ItemSlot {
    /// Build an `ItemSlot` from `(item_id, count, nbt)`. NBT is
    /// stored as-is to defer parsing cost.
    pub fn new(item_id: u32, count: u8, nbt: Option<Vec<u8>>) -> Self {
        Self {
            item_id,
            count,
            nbt,
        }
    }
}
