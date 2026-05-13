//! Standard leaf: FollowEntity. Look at the target entity and report
//! Success when within `distance`, Running otherwise. Mirrors Python
//! `behaviour/leaves.py::FollowEntity`.
//!
//! The leaf itself does not call `bot.walk_to` (that needs &mut Bot
//! which would require Arc<Mutex<Bot>> at the BT level). Users
//! either run this leaf inside a Repeater that ticks `walk_to`
//! externally, or build their own composite that owns &mut access.
//!
//! 004 Group I (T074).

use crate::behaviour::leaf::{BehaviourCtx, Leaf, NodeStatus};
use crate::bot::Bot;

/// Follow-entity leaf.
pub struct FollowEntity {
    /// Target entity id.
    pub eid: i32,
    /// Desired keep-distance in blocks.
    pub distance: f64,
}

impl FollowEntity {
    /// New leaf for entity `eid` with target keep-distance `distance`.
    pub fn new(eid: i32, distance: f64) -> Self {
        Self { eid, distance }
    }
}

#[async_trait::async_trait]
impl Leaf for FollowEntity {
    async fn tick(&mut self, bot: &Bot, _ctx: &BehaviourCtx) -> NodeStatus {
        let Some(target) = bot.entities_tracker.get(self.eid) else {
            return NodeStatus::Failure;
        };
        // Aim at the target on every tick — purely client-side, no
        // mutex required.
        if bot.look_at(target.x, target.y, target.z).await.is_err() {
            return NodeStatus::Failure;
        }
        let dist = bot.distance_to(self.eid).await.unwrap_or(f64::INFINITY);
        if dist <= self.distance {
            NodeStatus::Success
        } else {
            NodeStatus::Running
        }
    }
}
