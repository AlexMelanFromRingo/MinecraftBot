//! State accessors for [`Bot`]. Mirrors `python/minecraft_bot/bot.py` state
//! properties (x, y, z, yaw, pitch, on_ground, health, food, saturation,
//! is_dead, xp_level, xp_total, game_mode, held_slot, entity_id, world_name,
//! dimension).
//!
//! 004 Group A — to be filled in by T023..T027. The existing accessors
//! (`entity_id`, `health`, `food`, `position`) currently live in
//! `super` (`rust/src/bot.rs`) for backwards compatibility; this file
//! will receive the rest plus consolidated implementations.

#![allow(dead_code)]
