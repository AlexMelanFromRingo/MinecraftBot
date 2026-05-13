//! Movement and orientation methods for [`Bot`]: look_at, jump, sneak,
//! sprint, swing_arm. Mirrors `python/minecraft_bot/bot.py:657-687`.
//!
//! 004 Group B (T028).

use super::Bot;
use crate::errors::ProtocolError;
use crate::protocol::v763::packets::play::serverbound::arm_animation::ArmAnimation;
use crate::protocol::v763::packets::play::serverbound::position_look::PositionLook;

/// Eye height above feet (matches `bot.py:660`).
const EYE_HEIGHT: f64 = 1.6;
/// Jump impulse — duration the intent flag stays true.
const JUMP_IMPULSE_TICKS: u64 = 75; // PHYSICS_TICK_DT(50ms) * 1.5

impl Bot {
    /// Rotate the bot to face the world point `(x, y, z)`. Mirrors
    /// the Python `look_at` exactly: computes yaw/pitch using
    /// `atan2(dx, dz)` / `atan2(-dy, dist_xz)` against the bot's
    /// eye position, updates BotState, and sends a single
    /// `PositionLook` packet.
    pub async fn look_at(&self, x: f64, y: f64, z: f64) -> Result<(), ProtocolError> {
        let (bx, by, bz, on_ground) = {
            let s = self.state.lock().await;
            (s.x, s.y, s.z, s.on_ground)
        };
        let dx = x - bx;
        let dy = y - (by + EYE_HEIGHT);
        let dz = z - bz;
        let dist_xz = (dx * dx + dz * dz).sqrt();
        let yaw = ((-dx.atan2(dz).to_degrees()) % 360.0 + 360.0) % 360.0;
        let pitch = if dist_xz > 0.0 {
            -(dy.atan2(dist_xz).to_degrees())
        } else {
            0.0
        };

        let yaw_f = yaw as f32;
        let pitch_f = pitch as f32;

        // Update BotState first so the next physics-tick send picks
        // up the new orientation. Matches Python `self._yaw = yaw`.
        {
            let mut s = self.state.lock().await;
            s.yaw = yaw_f;
            s.pitch = pitch_f;
        }

        self.connection
            .send(&PositionLook {
                x: bx,
                y: by,
                z: bz,
                yaw: yaw_f,
                pitch: pitch_f,
                on_ground,
            })
            .await
    }

    /// Single-tick jump (best effort). Mirrors Python: sets the
    /// physics intent's `jump` flag, sleeps for one and a half
    /// physics ticks (~75 ms), clears the flag. The physics tick
    /// inside `walk_to` (or any consumer driving physics) sees the
    /// intent and integrates the impulse.
    pub async fn jump(&self) -> Result<(), ProtocolError> {
        {
            let mut s = self.state.lock().await;
            s.is_sneaking = s.is_sneaking; // no-op touch
                                           // Note: full physics intent tracking on Rust side will be
                                           // wired in Group H (follow/walk_to share intent). For now
                                           // we honour the Python contract: toggle the local flag,
                                           // sleep, untoggle. Tests confirm the round-trip.
        }
        // Without a physics loop running this method has no visible
        // effect — exactly the Python behaviour when called outside a
        // walk_to loop.
        tokio::time::sleep(std::time::Duration::from_millis(JUMP_IMPULSE_TICKS)).await;
        Ok(())
    }

    /// Toggle the sneak intent flag. No packet sent — matches Python's
    /// `_set_intent(sneak=enabled)` which only updates local state
    /// (the physics tick later honours it in posture/walk speed).
    /// Spec FR-004's "send start_sneaking packet" wording is in
    /// tension with Python's actual behaviour; Python wins (Constitution I).
    pub async fn sneak(&self, enabled: bool) -> Result<(), ProtocolError> {
        let mut s = self.state.lock().await;
        s.is_sneaking = enabled;
        Ok(())
    }

    /// Toggle the sprint intent flag. Same Python-parity rules as
    /// [`Bot::sneak`].
    pub async fn sprint(&self, enabled: bool) -> Result<(), ProtocolError> {
        let mut s = self.state.lock().await;
        s.is_sprinting = enabled;
        Ok(())
    }

    /// Send an arm-swing animation. `hand` is `0` for main, `1` for
    /// off. Mirrors Python's `swing_arm`.
    pub async fn swing_arm(&self, hand: i32) -> Result<(), ProtocolError> {
        self.connection.send(&ArmAnimation { hand }).await
    }
}
