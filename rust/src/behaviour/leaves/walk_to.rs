//! Standard leaf: WalkTo. Tracks an `(x, y, z)` goal and reports
//! Success once the bot is within 1 block, Running while in flight.
//! 004 Group I (T074).

use crate::behaviour::leaf::{BehaviourCtx, Leaf, NodeStatus};
use crate::bot::Bot;

/// Walk-to leaf.
pub struct WalkTo {
    /// Target world position.
    pub target: (f64, f64, f64),
    /// Latched flag — once arrived, subsequent ticks short-circuit.
    pub arrived: bool,
}

impl WalkTo {
    /// New walk-to leaf for target `(x, y, z)`.
    pub fn new(x: f64, y: f64, z: f64) -> Self {
        Self {
            target: (x, y, z),
            arrived: false,
        }
    }
}

#[async_trait::async_trait]
impl Leaf for WalkTo {
    async fn tick(&mut self, bot: &Bot, _ctx: &BehaviourCtx) -> NodeStatus {
        if self.arrived {
            return NodeStatus::Success;
        }
        let (tx, _ty, tz) = self.target;
        let (bx, _by, bz) = bot.position().await;
        let dx = tx - bx;
        let dz = tz - bz;
        if (dx * dx + dz * dz).sqrt() < 1.0 {
            self.arrived = true;
            return NodeStatus::Success;
        }
        NodeStatus::Running
    }

    fn reset(&mut self) {
        self.arrived = false;
    }
}
