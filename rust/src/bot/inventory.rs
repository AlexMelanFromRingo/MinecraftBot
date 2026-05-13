//! Inventory methods for [`Bot`]: held_item, find_item, count_item,
//! iter_accessible_slots, select_slot, drop_item, click_slot, move_item,
//! quick_move, equip_armor, unequip_armor, swap_to_offhand. Owns the
//! `InventoryState` dual-list per spec Q5. Filled in by 004 Group F
//! (T046..T057).
//!
//! Note: 003's `drop_held_item` currently lives in `super` and will be
//! reconciled with `drop_item` during Group F.

#![allow(dead_code)]
