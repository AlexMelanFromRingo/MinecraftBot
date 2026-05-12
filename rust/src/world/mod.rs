//! World cache and chunk storage — Rust port of
//! `python/minecraft_bot/world/`.
//!
//! Module layout mirrors the Python tree:
//! - `chunk.rs`        — `PalettedContainer`, `ChunkSection`, `Chunk`
//! - `block_table.rs`  — block-state classification table
//! - `cache.rs`        — `World` — voxel-snapshot keyed by `(cx, cz)`
//! - `decode_chunk.rs` — paletted-container parser (T025)

pub mod block_table;
pub mod cache;
pub mod chunk;
pub mod decode_chunk;

pub use cache::World;
pub use chunk::{BlockEntityRecord, Chunk, ChunkSection, PalettedContainer};
pub use decode_chunk::decode as decode_chunk;
