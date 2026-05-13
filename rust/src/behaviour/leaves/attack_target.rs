//! Standard leaf: AttackTarget. Look at the target entity and send
//! one attack per tick while it's tracked. Returns Failure when the
//! entity is no longer in the tracker. Mirrors Python
//! `behaviour/leaves.py::AttackTarget`.
//!
//! 004 Group I (T074).

use crate::behaviour::leaf::{BehaviourCtx, Leaf, NodeStatus};
use crate::bot::Bot;

/// Attack-target leaf.
pub struct AttackTarget {
    /// Target entity id.
    pub eid: i32,
}

impl AttackTarget {
    /// New leaf for entity `eid`.
    pub fn new(eid: i32) -> Self {
        Self { eid }
    }
}

#[async_trait::async_trait]
impl Leaf for AttackTarget {
    async fn tick(&mut self, bot: &Bot, _ctx: &BehaviourCtx) -> NodeStatus {
        let Some(target) = bot.entities_tracker.get(self.eid) else {
            return NodeStatus::Failure;
        };
        if bot.look_at(target.x, target.y, target.z).await.is_err() {
            return NodeStatus::Failure;
        }
        if bot.attack(self.eid).await.is_err() {
            return NodeStatus::Failure;
        }
        NodeStatus::Running
    }
}
