//! Food table loaded from `protocol-data/v763/items.json` — maps
//! Minecraft item id to `(hunger_restore, saturation_restore)`. Used
//! by `Bot::eat` to pick a food slot. Mirrors Python `foods.py`.
//!
//! 004 — populated by T017.

#![allow(dead_code)]

use std::collections::HashMap;
use std::sync::OnceLock;

/// One row of the food table.
#[derive(Clone, Debug)]
pub struct FoodEntry {
    /// Hunger points restored (0..20).
    pub hunger: u8,
    /// Saturation points restored.
    pub saturation: f32,
}

/// Lookup table indexed by Minecraft numeric item id (matches
/// `protocol-data/v763/items.json`).
#[derive(Debug, Default)]
pub struct FoodTable {
    by_item_id: HashMap<u32, FoodEntry>,
}

impl FoodTable {
    /// Lookup by numeric item id. Returns `None` for non-food items.
    pub fn get(&self, item_id: u32) -> Option<&FoodEntry> {
        self.by_item_id.get(&item_id)
    }

    /// Number of food entries (~40 for v763).
    pub fn len(&self) -> usize {
        self.by_item_id.len()
    }

    /// True if the table has not been populated.
    pub fn is_empty(&self) -> bool {
        self.by_item_id.is_empty()
    }
}

static FOOD_TABLE: OnceLock<FoodTable> = OnceLock::new();

/// Process-wide accessor. The first call lazily loads
/// `protocol-data/v763/items.json` (T017). Returns an empty table
/// until that landing.
pub fn food_table() -> &'static FoodTable {
    FOOD_TABLE.get_or_init(FoodTable::default)
}
