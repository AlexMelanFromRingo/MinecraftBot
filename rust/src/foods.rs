//! Food table loaded from `protocol-data/v763/food_table.json` — maps
//! Minecraft item id to `(food_points, saturation, modifier)`. Used
//! by `Bot::eat` to pick a food slot. Mirrors Python `foods.py`.
//!
//! 004 — T017.

#![allow(dead_code)]

use std::collections::HashMap;
use std::sync::OnceLock;

use serde::Deserialize;

/// One row of the food table.
#[derive(Clone, Debug)]
pub struct FoodEntry {
    /// Item registry name (e.g. `"minecraft:bread"`).
    pub name: String,
    /// Hunger points restored (0..20).
    pub food_points: u8,
    /// Saturation points restored.
    pub saturation: f32,
    /// Saturation-from-hunger modifier (Mojang's `saturation_modifier`).
    pub saturation_modifier: f32,
    /// Can be eaten even when hunger is full.
    pub can_always_eat: bool,
}

/// Lookup table indexed by Minecraft numeric item id (matches
/// `protocol-data/v763/item_table.json`).
#[derive(Debug, Default)]
pub struct FoodTable {
    by_item_id: HashMap<u32, FoodEntry>,
}

impl FoodTable {
    /// Lookup by numeric item id. Returns `None` for non-food items.
    pub fn get<I: std::borrow::Borrow<u32>>(&self, item_id: I) -> Option<&FoodEntry> {
        self.by_item_id.get(item_id.borrow())
    }

    /// Number of food entries (40 for v763).
    pub fn len(&self) -> usize {
        self.by_item_id.len()
    }

    /// True if the table has not been populated.
    pub fn is_empty(&self) -> bool {
        self.by_item_id.is_empty()
    }

    /// Iterate (item_id, entry) pairs.
    pub fn iter(&self) -> impl Iterator<Item = (&u32, &FoodEntry)> {
        self.by_item_id.iter()
    }
}

/// Embedded snapshot of `protocol-data/v763/food_table.json`. Embedding
/// keeps the standalone Rust crate self-contained — consumers don't
/// have to ship the JSON alongside the binary. The file is small
/// (~5 KiB) and rarely changes within a protocol version.
const FOOD_TABLE_JSON: &str =
    include_str!("../../protocol-data/v763/food_table.json");

#[derive(Deserialize)]
struct FoodRow {
    name: String,
    food_points: u8,
    saturation: f32,
    saturation_modifier: f32,
    can_always_eat: bool,
}

fn parse_food_table() -> FoodTable {
    let parsed: HashMap<String, FoodRow> = serde_json::from_str(FOOD_TABLE_JSON)
        .expect("protocol-data/v763/food_table.json must be valid JSON");
    let mut by_item_id = HashMap::with_capacity(parsed.len());
    for (id_str, row) in parsed {
        let id: u32 = id_str
            .parse()
            .expect("food_table.json keys must be numeric item ids");
        by_item_id.insert(
            id,
            FoodEntry {
                name: row.name,
                food_points: row.food_points,
                saturation: row.saturation,
                saturation_modifier: row.saturation_modifier,
                can_always_eat: row.can_always_eat,
            },
        );
    }
    FoodTable { by_item_id }
}

static FOOD_TABLE: OnceLock<FoodTable> = OnceLock::new();

/// Process-wide accessor. The first call lazily parses the embedded
/// snapshot of `protocol-data/v763/food_table.json`.
pub fn food_table() -> &'static FoodTable {
    FOOD_TABLE.get_or_init(parse_food_table)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bread_lookup() {
        let t = food_table();
        // bread is item id 853 in 1.20.1; sanity-check the loader by
        // verifying some known food has 5 food points (the canonical
        // Mojang value for bread).
        let bread_ids: Vec<u32> = t
            .iter()
            .filter(|(_, e)| e.name == "minecraft:bread")
            .map(|(id, _)| *id)
            .collect();
        assert_eq!(bread_ids.len(), 1, "bread should be in the food table");
        let bread = t.get(&bread_ids[0]).unwrap();
        assert_eq!(bread.food_points, 5, "bread = 5 food points");
    }

    #[test]
    fn table_populated() {
        let t = food_table();
        assert!(t.len() >= 30, "expected ~40 food entries, got {}", t.len());
    }
}
