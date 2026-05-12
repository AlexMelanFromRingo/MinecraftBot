//! World voxel-cache — Rust port of
//! `python/minecraft_bot/world/cache.py`.
//!
//! Kept in sync by the Connection's packet handlers (`map_chunk`,
//! `block_change`, `multi_block_change`, `unload_chunk`).
//! All access is through `&self` (interior mutability via
//! `parking_lot::RwLock`) so the Python-side `bot.world` object can
//! hand the same handle to multiple readers.

use std::collections::HashMap;

use parking_lot::RwLock;

use crate::world::block_table;
use crate::world::chunk::Chunk;

/// Bot's in-memory voxel snapshot.
pub struct World {
    chunks: RwLock<HashMap<(i32, i32), Chunk>>,
    config: RwLock<WorldConfig>,
}

#[derive(Debug, Clone)]
struct WorldConfig {
    dimension: String,
    min_y: i32,
    section_count: i32,
}

/// Lock-held view over a World's chunk map. While alive, no writer
/// can update the cache; every block-query is a plain `HashMap::get`
/// with no per-call lock acquisition. Holds for the duration of one
/// pathfinder or physics walk to amortise the lock cost across
/// thousands of block lookups.
pub struct WorldQueryGuard<'a> {
    chunks: parking_lot::RwLockReadGuard<'a, HashMap<(i32, i32), Chunk>>,
}

impl<'a> WorldQueryGuard<'a> {
    /// Block-state ID at `(x, y, z)`, or `0` (air) if the chunk is
    /// not loaded.
    #[inline]
    pub fn get_block_id(&self, x: i32, y: i32, z: i32) -> i32 {
        let cx = x >> 4;
        let cz = z >> 4;
        match self.chunks.get(&(cx, cz)) {
            Some(c) => c.get_block(x & 0xF, y, z & 0xF),
            None => 0,
        }
    }

    /// Predicate: solid block (no lock).
    #[inline]
    pub fn is_solid(&self, x: i32, y: i32, z: i32) -> bool {
        block_table::is_solid(self.get_block_id(x, y, z))
    }

    /// Predicate: water cell (no lock).
    #[inline]
    pub fn is_water(&self, x: i32, y: i32, z: i32) -> bool {
        block_table::is_water(self.get_block_id(x, y, z))
    }

    /// Predicate: navigable obstacle (no lock).
    #[inline]
    pub fn is_navigable_obstacle(&self, x: i32, y: i32, z: i32) -> bool {
        block_table::is_navigable_obstacle(self.get_block_id(x, y, z))
    }
}

impl World {
    /// Take a long-lived read guard over the chunk cache for fast
    /// repeated queries. Writers (packet handlers updating the World)
    /// block while the guard is alive; pathfinder / physics search
    /// holds the guard for the search duration (~milliseconds) so
    /// the contention window stays small.
    pub fn query_guard(&self) -> WorldQueryGuard<'_> {
        WorldQueryGuard {
            chunks: self.chunks.read(),
        }
    }
}

impl World {
    /// Construct an empty overworld-defaulted World.
    pub fn new() -> Self {
        Self::with_dimension("minecraft:overworld", -64, 24)
    }

    /// Construct with explicit dimension parameters.
    pub fn with_dimension(dimension: &str, min_y: i32, section_count: i32) -> Self {
        Self {
            chunks: RwLock::new(HashMap::new()),
            config: RwLock::new(WorldConfig {
                dimension: dimension.to_string(),
                min_y,
                section_count,
            }),
        }
    }

    /// Default vertical floor for newly-loaded chunks.
    pub fn min_y(&self) -> i32 {
        self.config.read().min_y
    }

    /// Default section count for newly-loaded chunks.
    pub fn section_count(&self) -> i32 {
        self.config.read().section_count
    }

    /// Current dimension identifier.
    pub fn dimension(&self) -> String {
        self.config.read().dimension.clone()
    }

    /// Number of loaded chunks.
    pub fn loaded_chunk_count(&self) -> usize {
        self.chunks.read().len()
    }

    /// Clone the chunk for `(cx, cz)` if loaded.
    pub fn get_chunk(&self, cx: i32, cz: i32) -> Option<Chunk> {
        self.chunks.read().get(&(cx, cz)).cloned()
    }

    /// Insert (or replace) a loaded chunk.
    pub fn insert_chunk(&self, chunk: Chunk) {
        let key = (chunk.cx, chunk.cz);
        self.chunks.write().insert(key, chunk);
    }

    /// Remove a chunk (server-driven unload).
    pub fn unload_chunk(&self, cx: i32, cz: i32) {
        self.chunks.write().remove(&(cx, cz));
    }

    /// Block-state ID at `(x, y, z)`, or `0` (air) if the chunk is
    /// not loaded or `y` is out of range.
    pub fn get_block_id(&self, x: i32, y: i32, z: i32) -> i32 {
        let cx = x >> 4;
        let cz = z >> 4;
        let chunks = self.chunks.read();
        match chunks.get(&(cx, cz)) {
            Some(c) => c.get_block(x & 0xF, y, z & 0xF),
            None => 0,
        }
    }

    /// Block name at `(x, y, z)`, or `None` if unknown.
    pub fn get_block_name(&self, x: i32, y: i32, z: i32) -> Option<&'static str> {
        block_table::get_name(self.get_block_id(x, y, z))
    }

    /// Single-block update (from `block_change`).
    pub fn set_block(&self, x: i32, y: i32, z: i32, state_id: i32) {
        let cx = x >> 4;
        let cz = z >> 4;
        let mut chunks = self.chunks.write();
        if let Some(c) = chunks.get_mut(&(cx, cz)) {
            c.set_block(x & 0xF, y, z & 0xF, state_id);
        }
    }

    /// Predicate: solid block (pathfinder/physics).
    pub fn is_solid(&self, x: i32, y: i32, z: i32) -> bool {
        block_table::is_solid(self.get_block_id(x, y, z))
    }

    /// Predicate: water cell.
    pub fn is_water(&self, x: i32, y: i32, z: i32) -> bool {
        block_table::is_water(self.get_block_id(x, y, z))
    }

    /// Predicate: navigable obstacle (door/gate/trapdoor).
    pub fn is_navigable_obstacle(&self, x: i32, y: i32, z: i32) -> bool {
        block_table::is_navigable_obstacle(self.get_block_id(x, y, z))
    }

    /// Reset cache (called on respawn / dimension change).
    pub fn reset(&self, dimension: Option<&str>, min_y: Option<i32>, section_count: Option<i32>) {
        self.chunks.write().clear();
        let mut cfg = self.config.write();
        if let Some(d) = dimension {
            cfg.dimension = d.to_string();
        }
        if let Some(y) = min_y {
            cfg.min_y = y;
        }
        if let Some(s) = section_count {
            cfg.section_count = s;
        }
    }

    /// Find up to `limit` blocks matching `name` within Chebyshev
    /// radius `radius` of `origin`, sorted by squared Euclidean distance.
    /// Mirrors `World.find_blocks_nearby` in the Python reference.
    pub fn find_blocks_nearby(
        &self,
        name: &str,
        origin: (f64, f64, f64),
        radius: i32,
        limit: usize,
    ) -> Vec<(i32, i32, i32)> {
        let normalised: String = if name.contains(':') {
            name.to_string()
        } else {
            format!("minecraft:{}", name)
        };
        let (ox, oy, oz) = origin;
        let cx0 = (ox as i32) >> 4;
        let cz0 = (oz as i32) >> 4;
        let cr = (radius + 15) >> 4;
        let cfg = self.config.read();
        let y_lo = ((oy - radius as f64) as i32).max(cfg.min_y);
        let y_hi = (((oy + radius as f64) as i32) + 1).min(cfg.min_y + cfg.section_count * 16);
        drop(cfg);
        let chunks = self.chunks.read();
        let mut matches: Vec<(f64, (i32, i32, i32))> = Vec::new();
        for dcx in -cr..=cr {
            for dcz in -cr..=cr {
                let Some(chunk) = chunks.get(&(cx0 + dcx, cz0 + dcz)) else {
                    continue;
                };
                let base_x = (cx0 + dcx) * 16;
                let base_z = (cz0 + dcz) * 16;
                for lx in 0..16 {
                    let wx = base_x + lx;
                    if ((wx as f64) - ox).abs() > radius as f64 {
                        continue;
                    }
                    for lz in 0..16 {
                        let wz = base_z + lz;
                        if ((wz as f64) - oz).abs() > radius as f64 {
                            continue;
                        }
                        for wy in y_lo..y_hi {
                            let sid = chunk.get_block(lx, wy, lz);
                            if block_table::get_name(sid) == Some(normalised.as_str()) {
                                let dx = wx as f64 - ox;
                                let dy = wy as f64 - oy;
                                let dz = wz as f64 - oz;
                                matches.push((dx * dx + dy * dy + dz * dz, (wx, wy, wz)));
                            }
                        }
                    }
                }
            }
        }
        matches.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));
        matches.into_iter().take(limit).map(|(_, p)| p).collect()
    }
}

impl Default for World {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::world::chunk::Chunk;

    #[test]
    fn empty_world_returns_air_everywhere() {
        let w = World::new();
        assert_eq!(w.get_block_id(0, 0, 0), 0);
        assert_eq!(w.get_block_id(123, 64, -456), 0);
        assert_eq!(w.loaded_chunk_count(), 0);
        assert!(!w.is_solid(0, 0, 0));
    }

    #[test]
    fn insert_and_query_chunk() {
        let w = World::new();
        let mut c = Chunk::empty(2, -3, -64, 24);
        // chunk (2, -3) covers world x ∈ [32, 47], z ∈ [-48, -33].
        c.set_block(0, 70, 0, 99);
        w.insert_chunk(c);
        assert_eq!(w.loaded_chunk_count(), 1);
        // World coord (32, 70, -48): cx=2, cz=-3, local (0, 70, 0).
        assert_eq!(w.get_block_id(32, 70, -48), 99);
        // Other chunk: still air.
        assert_eq!(w.get_block_id(100, 70, 100), 0);
    }

    #[test]
    fn unload_chunk_clears_state() {
        let w = World::new();
        w.insert_chunk(Chunk::empty(0, 0, -64, 24));
        assert_eq!(w.loaded_chunk_count(), 1);
        w.unload_chunk(0, 0);
        assert_eq!(w.loaded_chunk_count(), 0);
    }

    #[test]
    fn set_block_updates_loaded_chunk_only() {
        let w = World::new();
        w.insert_chunk(Chunk::empty(0, 0, -64, 24));
        w.set_block(5, 70, 7, 1); // stone
        assert_eq!(w.get_block_id(5, 70, 7), 1);
        // Unloaded chunk: no-op.
        w.set_block(100, 70, 100, 1);
        assert_eq!(w.get_block_id(100, 70, 100), 0);
    }
}
