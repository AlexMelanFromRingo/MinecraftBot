//! Hazard detection for walk_to — slab / water / ledge / drop checks.
//!
//! Returns classifications for cells the bot would step through.
//! `auto-step` and `auto-jump` are handled by `physics::tick`;
//! this module covers higher-level pre-flight checks (e.g. "would
//! the next waypoint drop the bot more than max_fall blocks?").

use crate::world::{block_table, World};

/// Hazard class at a specific cell.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Hazard {
    /// Safe to traverse at this height.
    None,
    /// Bottom slab — auto-step (physics handles).
    Slab,
    /// Water — slower travel; physics drag applies.
    Water,
    /// Ledge — solid block beside an air column.
    Ledge,
    /// Drop of more than `max_fall` blocks below.
    Drop,
    /// No floor anywhere in range — bot would fall.
    NoFloor,
}

/// Classify the hazard at `(x, y, z)` (the bot's feet) with the
/// given `max_fall` budget.
pub fn classify(world: &World, x: i32, y: i32, z: i32, max_fall: i32) -> Hazard {
    let below = world.get_block_id(x, y - 1, z);
    if block_table::is_water(below) || world.is_water(x, y, z) {
        return Hazard::Water;
    }
    if !block_table::is_solid(below) {
        // Search for a floor up to max_fall down.
        for d in 1..=max_fall {
            let id = world.get_block_id(x, y - 1 - d, z);
            if block_table::is_solid(id) {
                if d >= 1 {
                    return Hazard::Drop;
                }
                return Hazard::None;
            }
        }
        return Hazard::NoFloor;
    }
    // Solid floor. Check slab heuristic.
    let name = block_table::get_name(below);
    if let Some(n) = name {
        if n.ends_with("_slab") {
            return Hazard::Slab;
        }
    }
    Hazard::None
}

/// `true` if the bot can safely step onto `(x, y, z)`.
pub fn is_safe_step(world: &World, x: i32, y: i32, z: i32, max_fall: i32) -> bool {
    !matches!(classify(world, x, y, z, max_fall), Hazard::NoFloor)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::world::chunk::{Chunk, ChunkSection, PalettedContainer};

    fn world_with_floor(state_id: i32) -> World {
        let w = World::new();
        let mut c = Chunk::empty(0, 0, -64, 24);
        // Set y=0 to state_id at local (0,0).
        c.set_block(0, 0, 0, state_id);
        w.insert_chunk(c);
        w
    }

    #[test]
    fn solid_stone_floor_is_safe_none() {
        // state_id 1 = stone in v763
        let w = world_with_floor(1);
        assert_eq!(classify(&w, 0, 1, 0, 3), Hazard::None);
    }

    #[test]
    fn missing_floor_classifies_no_floor_or_drop() {
        let w = World::new();
        // Empty world — no chunks loaded; treat as air.
        let h = classify(&w, 0, 1, 0, 3);
        assert!(matches!(h, Hazard::NoFloor | Hazard::Drop));
    }

    // Slab classification requires a real state_id for `_slab`-named
    // blocks; covered by integration tests on real captures.
}
