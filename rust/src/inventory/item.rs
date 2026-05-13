//! `ItemSlot` value type — one Minecraft item-in-slot — plus the
//! item-id <-> name lookup table loaded once from
//! `protocol-data/v763/item_table.json`. Mirrors
//! `python/minecraft_bot/inventory/item.py::ItemSlot`.
//!
//! 004 — T019.

#![allow(dead_code)]

use std::collections::HashMap;
use std::sync::OnceLock;

use serde::Deserialize;

/// One item stack in an inventory slot.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ItemSlot {
    /// Numeric item id from `protocol-data/v763/item_table.json`.
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

    /// Resolve the Minecraft registry name (e.g. `"minecraft:bread"`)
    /// for this slot's item id. Returns `"minecraft:unknown_<id>"`
    /// for items not in the v763 item table — keeps the API total
    /// without panicking on a new datapack-added item.
    pub fn name(&self) -> String {
        item_table()
            .by_item_id
            .get(&self.item_id)
            .map(|row| row.name.clone())
            .unwrap_or_else(|| format!("minecraft:unknown_{}", self.item_id))
    }
}

/// Lookup table indexed by numeric item id.
#[derive(Debug)]
pub struct ItemTable {
    by_item_id: HashMap<u32, ItemRow>,
    by_name: HashMap<String, u32>,
}

#[derive(Clone, Debug, Deserialize)]
struct ItemRow {
    name: String,
    display_name: String,
    stack_size: u8,
}

impl ItemTable {
    /// Lookup numeric id by registry name.
    pub fn id_of(&self, name: &str) -> Option<u32> {
        self.by_name.get(name).copied()
    }

    /// Registry name from numeric id.
    pub fn name_of(&self, item_id: u32) -> Option<&str> {
        self.by_item_id.get(&item_id).map(|r| r.name.as_str())
    }

    /// Stack size for an item id.
    pub fn stack_size(&self, item_id: u32) -> Option<u8> {
        self.by_item_id.get(&item_id).map(|r| r.stack_size)
    }

    /// Number of items in the table (1255 for v763).
    pub fn len(&self) -> usize {
        self.by_item_id.len()
    }

    /// True if not yet loaded.
    pub fn is_empty(&self) -> bool {
        self.by_item_id.is_empty()
    }
}

const ITEM_TABLE_JSON: &str =
    include_str!("../../../protocol-data/v763/item_table.json");

fn parse_item_table() -> ItemTable {
    let parsed: HashMap<String, ItemRow> = serde_json::from_str(ITEM_TABLE_JSON)
        .expect("protocol-data/v763/item_table.json must be valid JSON");
    let mut by_item_id = HashMap::with_capacity(parsed.len());
    let mut by_name = HashMap::with_capacity(parsed.len());
    for (id_str, row) in parsed {
        let id: u32 = id_str
            .parse()
            .expect("item_table.json keys must be numeric item ids");
        by_name.insert(row.name.clone(), id);
        by_item_id.insert(id, row);
    }
    ItemTable {
        by_item_id,
        by_name,
    }
}

static ITEM_TABLE: OnceLock<ItemTable> = OnceLock::new();

/// Process-wide accessor for the item-id <-> name table.
pub fn item_table() -> &'static ItemTable {
    ITEM_TABLE.get_or_init(parse_item_table)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn item_table_known_lookups() {
        let t = item_table();
        assert_eq!(t.name_of(0).unwrap(), "minecraft:air");
        assert_eq!(t.name_of(1).unwrap(), "minecraft:stone");
        // Lookup by name should round-trip.
        let stone_id = t.id_of("minecraft:stone").unwrap();
        assert_eq!(t.name_of(stone_id).unwrap(), "minecraft:stone");
    }

    #[test]
    fn itemslot_name_unknown_fallback() {
        let s = ItemSlot::new(99_999, 1, None);
        assert_eq!(s.name(), "minecraft:unknown_99999");
    }

    #[test]
    fn itemslot_name_known() {
        let air = ItemSlot::new(0, 1, None);
        assert_eq!(air.name(), "minecraft:air");
    }
}
