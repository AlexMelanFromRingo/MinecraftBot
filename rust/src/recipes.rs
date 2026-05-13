//! Recipe index loaded from `protocol-data/v763/recipes.json`. Used
//! by `Bot::craft` to resolve a 3x3 grid -> recipe id + output item.
//!
//! 004 — populated by T018.

#![allow(dead_code)]

use std::collections::HashMap;
use std::sync::OnceLock;

/// One recipe row.
#[derive(Clone, Debug)]
pub struct RecipeEntry {
    /// Recipe identifier (e.g. `"minecraft:crafting_table"`).
    pub recipe_id: String,
    /// Output item name (e.g. `"minecraft:crafting_table"`).
    pub output_item: String,
    /// Number of output items produced per craft.
    pub output_count: u32,
    /// Verification grid — the same row-major 9-cell layout the
    /// caller supplied. Used to defend against hash collisions.
    pub grid_signature: [Option<String>; 9],
}

/// Index of recipes keyed by the hash of their row-major 9-cell
/// grid (with `None` rendered as empty string before hashing).
#[derive(Debug, Default)]
pub struct RecipeIndex {
    by_grid_hash: HashMap<u64, RecipeEntry>,
}

impl RecipeIndex {
    /// Find a recipe whose grid matches `grid`. Returns `None` if
    /// no recipe is registered for the layout.
    pub fn lookup(&self, grid: &[Option<String>; 9]) -> Option<&RecipeEntry> {
        let hash = hash_grid(grid);
        let entry = self.by_grid_hash.get(&hash)?;
        // Verify against the collision-defence signature.
        if entry.grid_signature == *grid {
            Some(entry)
        } else {
            None
        }
    }

    /// Number of indexed recipes.
    pub fn len(&self) -> usize {
        self.by_grid_hash.len()
    }

    /// True if the index has not been populated.
    pub fn is_empty(&self) -> bool {
        self.by_grid_hash.is_empty()
    }
}

/// Compute the hash key used by [`RecipeIndex`].
pub(crate) fn hash_grid(grid: &[Option<String>; 9]) -> u64 {
    use std::hash::{Hash, Hasher};
    let mut h = std::collections::hash_map::DefaultHasher::new();
    for cell in grid {
        match cell {
            Some(s) => s.hash(&mut h),
            None => "".hash(&mut h),
        }
    }
    h.finish()
}

static RECIPE_INDEX: OnceLock<RecipeIndex> = OnceLock::new();

/// Process-wide accessor. The first call lazily loads
/// `protocol-data/v763/recipes.json` (T018). Returns an empty
/// index until that landing.
pub fn recipe_index() -> &'static RecipeIndex {
    RECIPE_INDEX.get_or_init(RecipeIndex::default)
}
