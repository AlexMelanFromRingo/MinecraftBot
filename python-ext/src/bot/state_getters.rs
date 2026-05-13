//! Sync `#[getter]` accessors for `PyBot`, satisfying Q1: Python user
//! scripts read `bot.x`, `bot.health`, etc. as plain attributes
//! (no `await`). Each getter calls `py.allow_threads` to release the
//! GIL and drives the Rust async accessor through the process-wide
//! tokio runtime to completion. See research.md R-1.
//!
//! 004 — T025.

use pyo3::prelude::*;

use super::PyBot;
use crate::runtime;

#[pymethods]
impl PyBot {
    /// Server-assigned entity id (from Login packet), or None pre-login.
    #[getter]
    fn entity_id(&self, py: Python<'_>) -> Option<i32> {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.entity_id().await
            })
        })
    }

    /// Last-known health (0..20).
    #[getter]
    fn health(&self, py: Python<'_>) -> f32 {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.health().await
            })
        })
    }

    /// Last-known food (0..20).
    #[getter]
    fn food(&self, py: Python<'_>) -> i32 {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.food().await
            })
        })
    }

    /// Last-known `(x, y, z)` position. Defaults to `(0.0, 64.0, 0.5)`
    /// pre-connect, matching the Python ref's PhysicsState defaults.
    #[getter]
    fn position(&self, py: Python<'_>) -> (f64, f64, f64) {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.position().await
            })
        })
    }

    /// X coordinate (sync property — matches `minecraft_bot.Bot.x`).
    #[getter]
    fn x(&self, py: Python<'_>) -> f64 {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.x().await
            })
        })
    }

    /// Y coordinate.
    #[getter]
    fn y(&self, py: Python<'_>) -> f64 {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.y().await
            })
        })
    }

    /// Z coordinate.
    #[getter]
    fn z(&self, py: Python<'_>) -> f64 {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.z().await
            })
        })
    }

    /// Yaw in degrees.
    #[getter]
    fn yaw(&self, py: Python<'_>) -> f32 {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.yaw().await
            })
        })
    }

    /// Pitch in degrees.
    #[getter]
    fn pitch(&self, py: Python<'_>) -> f32 {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.pitch().await
            })
        })
    }

    /// Whether the bot is on the ground.
    #[getter]
    fn on_ground(&self, py: Python<'_>) -> bool {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.on_ground().await
            })
        })
    }

    /// Current saturation.
    #[getter]
    fn saturation(&self, py: Python<'_>) -> f32 {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.saturation().await
            })
        })
    }

    /// True iff health <= 0.
    #[getter]
    fn is_dead(&self, py: Python<'_>) -> bool {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.is_dead().await
            })
        })
    }

    /// Experience level (green number).
    #[getter]
    fn xp_level(&self, py: Python<'_>) -> i32 {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.xp_level().await
            })
        })
    }

    /// Lifetime experience total.
    #[getter]
    fn xp_total(&self, py: Python<'_>) -> i32 {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.xp_total().await
            })
        })
    }

    /// Game mode (0..3, or None pre-Login).
    #[getter]
    fn game_mode(&self, py: Python<'_>) -> Option<u8> {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.game_mode().await
            })
        })
    }

    /// Hotbar slot 0..8.
    #[getter]
    fn held_slot(&self, py: Python<'_>) -> u8 {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.held_slot().await
            })
        })
    }

    /// World identifier (e.g. `"minecraft:overworld"`).
    #[getter]
    fn world_name(&self, py: Python<'_>) -> Option<String> {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.world_name().await
            })
        })
    }

    /// Dimension identifier.
    #[getter]
    fn dimension(&self, py: Python<'_>) -> Option<String> {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.dimension().await
            })
        })
    }

    /// Sneak toggle state (set by `sneak(true|false)`).
    #[getter]
    fn is_sneaking(&self, py: Python<'_>) -> bool {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.is_sneaking().await
            })
        })
    }

    /// Sprint toggle state (set by `sprint(true|false)`).
    #[getter]
    fn is_sprinting(&self, py: Python<'_>) -> bool {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.is_sprinting().await
            })
        })
    }
}
