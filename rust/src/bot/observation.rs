//! Observation & snapshot methods for [`Bot`] (FR-019, FR-020).
//! Mirrors `python/minecraft_bot/bot.py:745` (snapshot) and `:803`
//! (observation). Returns rich dict-like structs that the accel
//! layer exposes as Python dicts.
//!
//! 004 Group E (T043).

use super::Bot;
use crate::entities::Entity;

/// Frozen view of the bot's full state.
#[derive(Debug, Clone, Default)]
pub struct BotSnapshot {
    /// Position (x, y, z).
    pub position: (f64, f64, f64),
    /// Look orientation (yaw, pitch).
    pub orientation: (f32, f32),
    /// On-ground flag.
    pub on_ground: bool,
    /// Health.
    pub health: f32,
    /// Food.
    pub food: i32,
    /// Saturation.
    pub saturation: f32,
    /// Held hotbar slot 0..8.
    pub held_slot: u8,
    /// Snapshot of nearby entities (within `nearby_radius`).
    pub nearby_entities: Vec<Entity>,
}

/// Lighter-weight observation for AI loops.
#[derive(Debug, Clone, Default)]
pub struct Observation {
    /// Position.
    pub position: (f64, f64, f64),
    /// Look orientation.
    pub orientation: (f32, f32),
    /// Health.
    pub health: f32,
    /// Food.
    pub food: i32,
    /// Voxel grid around the bot (flat row-major, `[y][z][x]`).
    pub voxel_grid: Vec<i32>,
    /// `(side, side, side)` shape of `voxel_grid`.
    pub voxel_shape: (usize, usize, usize),
    /// First-hit raycast from the bot's eye, if any.
    pub look_hit: Option<(i32, i32, i32, i32, u8)>,
    /// Nearby entity snapshot (limited to nearby_radius).
    pub nearby_entities: Vec<Entity>,
}

impl Bot {
    /// Capture a frozen snapshot of the bot's full state.
    pub async fn snapshot(&self, nearby_radius: f64) -> BotSnapshot {
        let (x, y, z, yaw, pitch, on_ground, health, food, saturation, held_slot) = {
            let s = self.state.lock().await;
            (
                s.x,
                s.y,
                s.z,
                s.yaw,
                s.pitch,
                s.on_ground,
                s.health,
                s.food,
                s.saturation,
                s.held_slot,
            )
        };
        let nearby_entities = self
            .entities_tracker
            .nearby_entities((x, y, z), nearby_radius);
        BotSnapshot {
            position: (x, y, z),
            orientation: (yaw, pitch),
            on_ground,
            health,
            food,
            saturation,
            held_slot,
            nearby_entities,
        }
    }

    /// Compose a per-tick observation for AI loops.
    pub async fn observation(
        &self,
        voxel_radius: i32,
        nearby_radius: f64,
        look_distance: f64,
    ) -> Observation {
        let (x, y, z, yaw, pitch, health, food) = {
            let s = self.state.lock().await;
            (s.x, s.y, s.z, s.yaw, s.pitch, s.health, s.food)
        };
        let (voxel_grid, side) = self.voxel_grid(voxel_radius).await;
        let look_hit = self
            .raycast(look_distance)
            .await
            .map(|(bx, by, bz, st, face)| (bx, by, bz, st, face));
        let nearby_entities = self
            .entities_tracker
            .nearby_entities((x, y, z), nearby_radius);
        Observation {
            position: (x, y, z),
            orientation: (yaw, pitch),
            health,
            food,
            voxel_grid,
            voxel_shape: (side, side, side),
            look_hit,
            nearby_entities,
        }
    }
}
