//! State accessors for [`Bot`]. Mirrors `python/minecraft_bot/bot.py`
//! @property fields: x, y, z, yaw, pitch, on_ground, health, food,
//! saturation, is_dead, xp_level, xp_total, game_mode, held_slot,
//! entity_id, world_name, dimension. Plus the `position` 3-tuple
//! accessor.
//!
//! All accessors are `async fn` on the Rust side (R-1). The accel
//! facade wraps each one in a `#[getter]` sync property so existing
//! Python user scripts keep working with `bot.x` (no `await`) when
//! the import is swapped.
//!
//! 004 — T024.

use super::Bot;

impl Bot {
    /// X coordinate of the bot's feet position.
    pub async fn x(&self) -> f64 {
        self.state.lock().await.x
    }

    /// Y coordinate (feet altitude).
    pub async fn y(&self) -> f64 {
        self.state.lock().await.y
    }

    /// Z coordinate.
    pub async fn z(&self) -> f64 {
        self.state.lock().await.z
    }

    /// Yaw rotation (degrees, 0 = south, positive = clockwise looking down).
    pub async fn yaw(&self) -> f32 {
        self.state.lock().await.yaw
    }

    /// Pitch rotation (degrees, 0 = level, -90 = straight up).
    pub async fn pitch(&self) -> f32 {
        self.state.lock().await.pitch
    }

    /// Whether the bot is touching the ground (mirror of physics state).
    pub async fn on_ground(&self) -> bool {
        self.state.lock().await.on_ground
    }

    /// Current saturation (0..20). Used together with food to predict
    /// hunger drain.
    pub async fn saturation(&self) -> f32 {
        self.state.lock().await.saturation
    }

    /// `true` iff the bot's health is at or below zero.
    pub async fn is_dead(&self) -> bool {
        self.state.lock().await.health <= 0.0
    }

    /// Current experience level (the big green number).
    pub async fn xp_level(&self) -> i32 {
        self.state.lock().await.xp_level
    }

    /// Lifetime total experience (sum of all levels gained).
    pub async fn xp_total(&self) -> i32 {
        self.state.lock().await.xp_total
    }

    /// Current game mode (0=survival, 1=creative, 2=adventure,
    /// 3=spectator). `None` until the server has sent the initial
    /// `Login` packet.
    pub async fn game_mode(&self) -> Option<u8> {
        self.state.lock().await.game_mode
    }

    /// Active hotbar slot (0..8).
    pub async fn held_slot(&self) -> u8 {
        self.state.lock().await.held_slot
    }

    /// Current world identifier (e.g. `"minecraft:overworld"`).
    /// `None` before the initial `Login` packet.
    pub async fn world_name(&self) -> Option<String> {
        self.state.lock().await.world_name.clone()
    }

    /// Current dimension identifier (often the same as world_name
    /// for vanilla servers). `None` before `Login`.
    pub async fn dimension(&self) -> Option<String> {
        self.state.lock().await.dimension.clone()
    }

    /// Whether the bot is currently sneaking (toggled by `sneak()`).
    /// 004 Group B will write this field; until then it stays false.
    pub async fn is_sneaking(&self) -> bool {
        self.state.lock().await.is_sneaking
    }

    /// Whether the bot is currently sprinting (toggled by `sprint()`).
    pub async fn is_sprinting(&self) -> bool {
        self.state.lock().await.is_sprinting
    }
}
