//! Standard leaf: `attack_target`. MVP stub returning Running; behavioural
//! parity with the Python leaf is a backlog polish item.
//! 004 Group I (T074).

use crate::behaviour::leaf::{BehaviourCtx, Leaf, NodeStatus};
use crate::bot::Bot;

/// Placeholder leaf.
pub struct AttackTarget {
    pub eid: Option<i32>,
}

impl AttackTarget {
    /// New placeholder leaf.
    pub fn new() -> Self {
        Self { eid: None }
    }
}

#[async_trait::async_trait]
impl Leaf for AttackTarget {
    async fn tick(&mut self, _bot: &Bot, _ctx: &BehaviourCtx) -> NodeStatus {
        NodeStatus::Running
    }
}
