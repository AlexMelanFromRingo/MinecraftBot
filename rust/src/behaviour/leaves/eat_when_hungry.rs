//! Standard leaf: EatWhenHungry. Calls `bot.eat()` whenever the
//! bot's food level drops below `threshold`. Mirrors Python
//! `behaviour/leaves.py::EatWhenHungry`.
//!
//! 004 Group I (T074).

use std::time::Duration;

use crate::behaviour::leaf::{BehaviourCtx, Leaf, NodeStatus};
use crate::bot::Bot;

/// Auto-eat leaf.
pub struct EatWhenHungry {
    /// Hunger threshold (0..20). Eats when `bot.food < threshold`.
    pub threshold: i32,
}

impl EatWhenHungry {
    /// New leaf with the given hunger threshold (typical: 15).
    pub fn new(threshold: i32) -> Self {
        Self { threshold }
    }
}

#[async_trait::async_trait]
impl Leaf for EatWhenHungry {
    async fn tick(&mut self, bot: &Bot, _ctx: &BehaviourCtx) -> NodeStatus {
        if bot.food().await >= self.threshold {
            return NodeStatus::Success;
        }
        match bot.eat(Duration::from_secs_f64(3.0)).await {
            Ok(()) => NodeStatus::Success,
            Err(_) => NodeStatus::Failure,
        }
    }
}
