//! Inventory module — `ItemSlot` value type, click-sequence helpers,
//! and inventory state transitions. Mirrors
//! `python/minecraft_bot/inventory/`.
//!
//! 004 — populated by T019..T020. The `InventoryState` struct itself
//! lives on `Bot` (in `bot/inventory.rs`) since it needs access to
//! the dispatcher; the helpers in `click.rs` are pure functions.

#![allow(dead_code)]

pub mod click;
pub mod item;

pub use item::ItemSlot;
