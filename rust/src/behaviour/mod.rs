//! Behaviour layer — hazard detection (003) + behaviour-tree primitives (004).
//!
//! 004 additions: `Leaf` trait, `Selector`, `Sequencer`, `Inverter`,
//! `Repeater`, `BehaviourRunner`, `NodeStatus`, `BehaviourCtx`,
//! `BehaviourValue`. Filled in by 004 Group I (T072..T077). The
//! standard leaves (`WalkTo`, `EatWhenHungry`, `FollowEntity`,
//! `AttackTarget`) live under `behaviour::leaves::`.

pub mod hazards;
pub mod leaf;
pub mod leaves;

pub use leaf::{BehaviourCtx, BehaviourValue, Leaf, NodeStatus};
