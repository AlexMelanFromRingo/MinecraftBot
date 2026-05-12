//! Chunk storage — Rust port of `python/minecraft_bot/world/chunk.py`.
//!
//! Coordinate conventions match the Python reference exactly:
//! - `cx = x >> 4`, `cz = z >> 4`
//! - `local_x = x & 15`, `local_z = z & 15`
//! - `section_idx = (y - min_y) >> 4`
//! - `local_y = (y - min_y) & 15`
//!
//! Overworld defaults for protocol 763: `min_y = -64`, `section_count
//! = 24` (384 blocks of height).

use std::collections::HashMap;

/// Per-section paletted storage.
///
/// Three modes (decided at decode time):
/// - **single-value**: every cell shares one value. `palette` and
///   `data` are empty; `single_value` is `Some`.
/// - **indexed**: `palette` is the value table; `data` is a packed
///   long array of palette indices; `bits_per_entry > 0`.
/// - **direct**: `palette` is empty; `data` packs raw values directly
///   at `bits_per_entry` width.
///
/// Default is single-value mode holding `0` (air for block states /
/// plains for biomes). This matches the Python reference's
/// dataclass-default behaviour where a fresh `ChunkSection` reads as
/// all-air without explicit initialisation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PalettedContainer {
    /// Bits per packed entry. `0` only in single-value mode.
    pub bits_per_entry: u8,
    /// Palette table (empty in single-value / direct modes).
    pub palette: Vec<i32>,
    /// Packed long array (empty in single-value mode).
    pub data: Vec<i64>,
    /// In single-value mode, the constant value; otherwise `None`.
    pub single_value: Option<i32>,
}

impl Default for PalettedContainer {
    fn default() -> Self {
        Self::single(0)
    }
}

impl PalettedContainer {
    /// Construct a single-value container holding `value` across all
    /// cells. The grid size is implicit; the caller picks up cell
    /// counts from the surrounding [`ChunkSection`].
    pub fn single(value: i32) -> Self {
        Self {
            bits_per_entry: 0,
            palette: Vec::new(),
            data: Vec::new(),
            single_value: Some(value),
        }
    }

    /// Construct an indexed container.
    pub fn indexed(bits_per_entry: u8, palette: Vec<i32>, data: Vec<i64>) -> Self {
        Self { bits_per_entry, palette, data, single_value: None }
    }

    /// Construct a direct-mode container.
    pub fn direct(bits_per_entry: u8, data: Vec<i64>) -> Self {
        Self { bits_per_entry, palette: Vec::new(), data, single_value: None }
    }

    /// Read the value at flat `index`. Out-of-range palette indices
    /// silently fold to `0` (air-ish), matching the Python reference.
    pub fn get(&self, index: usize) -> i32 {
        if let Some(v) = self.single_value {
            return v;
        }
        if self.bits_per_entry == 0 || self.data.is_empty() {
            return 0;
        }
        let bpe = self.bits_per_entry as usize;
        let entries_per_long = 64usize / bpe;
        let long_idx = index / entries_per_long;
        let sub_idx = index % entries_per_long;
        let mask: i64 = (1i64 << bpe) - 1;
        if long_idx >= self.data.len() {
            return 0;
        }
        let raw = ((self.data[long_idx] >> (sub_idx * bpe)) & mask) as i32;
        if !self.palette.is_empty() {
            if (raw as usize) >= self.palette.len() {
                return 0;
            }
            self.palette[raw as usize]
        } else {
            raw
        }
    }

    /// Write `value` at flat `index`. Promotes single-value mode to
    /// direct-15-bit on first mutation, matching the Python reference.
    pub fn set(&mut self, index: usize, value: i32) {
        if let Some(sv) = self.single_value {
            if value == sv {
                return;
            }
            // Promote to direct-15-bit, pre-filled with `sv`.
            self.promote_single_to_direct(sv);
        }
        let bpe = self.bits_per_entry as usize;
        let entries_per_long = 64usize / bpe;
        let long_idx = index / entries_per_long;
        let sub_idx = index % entries_per_long;
        let mask: i64 = (1i64 << bpe) - 1;
        let raw: i64 = if !self.palette.is_empty() {
            // Indexed mode: find or append.
            if let Some(pos) = self.palette.iter().position(|v| *v == value) {
                pos as i64
            } else {
                let pos = self.palette.len() as i64;
                self.palette.push(value);
                if pos > mask {
                    // Palette overflow → promote to direct mode.
                    self.promote_indexed_to_direct();
                    return self.set(index, value);
                }
                pos
            }
        } else {
            (value as i64) & mask
        };
        let cleared = self.data[long_idx] & !(mask << (sub_idx * bpe));
        self.data[long_idx] = cleared | ((raw & mask) << (sub_idx * bpe));
    }

    fn promote_single_to_direct(&mut self, sv: i32) {
        let n_cells: usize = 4096; // 16×16×16
        let bpe: usize = 15;
        let entries_per_long = 64 / bpe;
        let n_longs = n_cells.div_ceil(entries_per_long);
        let mask: i64 = (1i64 << bpe) - 1;
        let mut data = Vec::with_capacity(n_longs);
        let v = (sv as i64) & mask;
        for _ in 0..n_longs {
            let mut packed: i64 = 0;
            for slot in 0..entries_per_long {
                packed |= v << (slot * bpe);
            }
            data.push(packed);
        }
        self.bits_per_entry = bpe as u8;
        self.palette = Vec::new();
        self.data = data;
        self.single_value = None;
    }

    fn promote_indexed_to_direct(&mut self) {
        let n_cells: usize = 4096;
        let old_bpe = self.bits_per_entry as usize;
        let old_palette = std::mem::take(&mut self.palette);
        let old_data = std::mem::take(&mut self.data);
        let old_eppl = 64usize / old_bpe;
        let old_mask: i64 = (1i64 << old_bpe) - 1;
        let mut values = Vec::with_capacity(n_cells);
        for i in 0..n_cells {
            let li = i / old_eppl;
            let si = i % old_eppl;
            let raw = if li < old_data.len() {
                ((old_data[li] >> (si * old_bpe)) & old_mask) as i32
            } else {
                0
            };
            let v = if (raw as usize) < old_palette.len() {
                old_palette[raw as usize]
            } else {
                0
            };
            values.push(v);
        }
        let new_bpe: usize = 15;
        let new_eppl = 64usize / new_bpe;
        let new_mask: i64 = (1i64 << new_bpe) - 1;
        let n_longs = n_cells.div_ceil(new_eppl);
        let mut new_data = vec![0i64; n_longs];
        for (i, &v) in values.iter().enumerate() {
            let li = i / new_eppl;
            let si = i % new_eppl;
            new_data[li] |= ((v as i64) & new_mask) << (si * new_bpe);
        }
        self.bits_per_entry = new_bpe as u8;
        self.palette = Vec::new();
        self.data = new_data;
    }
}

/// 16×16×16 paletted block-state + 4×4×4 paletted biome cells.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ChunkSection {
    /// Cached count of non-air blocks (server-provided; informational).
    pub block_count: i32,
    /// Paletted 16×16×16 block-state grid.
    pub block_states: PalettedContainer,
    /// Paletted 4×4×4 biome grid.
    pub biomes: PalettedContainer,
}

impl ChunkSection {
    /// Read block-state ID at local section coordinates (0..15).
    pub fn get_block(&self, lx: i32, ly: i32, lz: i32) -> i32 {
        let idx = ((ly as usize) << 8) | ((lz as usize) << 4) | (lx as usize);
        self.block_states.get(idx)
    }

    /// Set block-state ID at local section coordinates (0..15).
    pub fn set_block(&mut self, lx: i32, ly: i32, lz: i32, state_id: i32) {
        let idx = ((ly as usize) << 8) | ((lz as usize) << 4) | (lx as usize);
        self.block_states.set(idx, state_id);
    }
}

/// A block-entity (sign, chest, banner, …) record within a chunk.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BlockEntityRecord {
    /// World x.
    pub x: i32,
    /// World y.
    pub y: i32,
    /// World z.
    pub z: i32,
    /// Block-entity registry id.
    pub type_id: i32,
    /// Hex-encoded NBT payload (kept opaque; parsed by callers).
    pub nbt: Vec<u8>,
}

/// A 16×N×16 chunk.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Chunk {
    /// Chunk x (`x >> 4`).
    pub cx: i32,
    /// Chunk z (`z >> 4`).
    pub cz: i32,
    /// Vertical stack of sections (length = `section_count`).
    pub sections: Vec<ChunkSection>,
    /// Block-entities keyed by world (x, y, z).
    pub block_entities: HashMap<(i32, i32, i32), BlockEntityRecord>,
    /// Raw heightmaps NBT payload (opaque for now).
    pub heightmaps: Vec<u8>,
    /// World-y of the bottom of the chunk (e.g., `-64` for overworld).
    pub min_y: i32,
    /// Number of sections stacked vertically.
    pub section_count: i32,
}

impl Chunk {
    /// Construct an empty chunk for `(cx, cz)`. All sections default
    /// to single-value air (`state_id = 0`).
    pub fn empty(cx: i32, cz: i32, min_y: i32, section_count: i32) -> Self {
        let sections = (0..section_count).map(|_| ChunkSection::default()).collect();
        Self {
            cx,
            cz,
            sections,
            block_entities: HashMap::new(),
            heightmaps: Vec::new(),
            min_y,
            section_count,
        }
    }

    /// Get block-state at chunk-local `(lx, lz)` and world `y`.
    /// Returns `0` (air) for y outside the loaded range.
    pub fn get_block(&self, local_x: i32, y: i32, local_z: i32) -> i32 {
        let section_idx = ((y - self.min_y) >> 4) as i32;
        if section_idx < 0 || (section_idx as usize) >= self.sections.len() {
            return 0;
        }
        let ly = (y - self.min_y) & 15;
        self.sections[section_idx as usize].get_block(local_x, ly, local_z)
    }

    /// Set block-state at chunk-local `(lx, lz)` and world `y`.
    /// No-op for y outside the loaded range.
    pub fn set_block(&mut self, local_x: i32, y: i32, local_z: i32, state_id: i32) {
        let section_idx = ((y - self.min_y) >> 4) as i32;
        if section_idx < 0 || (section_idx as usize) >= self.sections.len() {
            return;
        }
        let ly = (y - self.min_y) & 15;
        self.sections[section_idx as usize].set_block(local_x, ly, local_z, state_id);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn paletted_single_value_get_returns_constant() {
        let p = PalettedContainer::single(7);
        for i in 0..4096 {
            assert_eq!(p.get(i), 7);
        }
    }

    #[test]
    fn paletted_single_promote_to_direct_on_first_set() {
        let mut p = PalettedContainer::single(3);
        p.set(100, 5);
        assert_eq!(p.get(100), 5);
        // Other cells still hold the old value.
        assert_eq!(p.get(0), 3);
        assert_eq!(p.get(4095), 3);
    }

    #[test]
    fn paletted_indexed_round_trip() {
        let palette = vec![100, 200, 300];
        // 16 cells per long at 4 bits per entry; entry 0..2 mapped to
        // palette indices 0, 1, 2.
        let mut data = vec![0i64];
        // bits=4, so cell 0 holds bits 0..4, cell 1 holds bits 4..8, …
        data[0] = (0) | (1 << 4) | (2 << 8);
        let p = PalettedContainer::indexed(4, palette, data);
        assert_eq!(p.get(0), 100);
        assert_eq!(p.get(1), 200);
        assert_eq!(p.get(2), 300);
    }

    #[test]
    fn chunk_section_get_set_local_coords() {
        let mut s = ChunkSection::default();
        s.set_block(7, 3, 12, 42);
        assert_eq!(s.get_block(7, 3, 12), 42);
        // Unrelated cell still air.
        assert_eq!(s.get_block(0, 0, 0), 0);
    }

    #[test]
    fn chunk_get_set_across_sections() {
        let mut c = Chunk::empty(0, 0, -64, 24);
        // Set a block at world-y 100. section_idx = (100 - (-64)) >> 4 = 164 >> 4 = 10
        c.set_block(5, 100, 9, 99);
        assert_eq!(c.get_block(5, 100, 9), 99);
        // Below the chunk: out of range, returns 0.
        assert_eq!(c.get_block(5, -100, 9), 0);
        // Above the chunk: out of range, returns 0.
        assert_eq!(c.get_block(5, 1000, 9), 0);
    }
}
