//! Behaviour-tree leaf trait and shared value types.
//!
//! `BehaviourValue` is a closed enum so the pure-Rust crate stays
//! free of pyo3 — the accel facade converts to/from a Python dict at
//! the boundary (see specs/004-full-bot-parity/research.md R-6).
//!
//! Standard `NodeStatus` names per the BT literature: `Running` means
//! "tick me again next time"; `Success`/`Failure` are terminal.

#![allow(dead_code)]

use std::collections::HashMap;
use std::sync::Arc;

use parking_lot::RwLock;

/// Value type carried by the behaviour-tree shared context.
///
/// Closed by design — adding a new variant requires bumping the
/// 004 contract. The `Json` fallback handles nested dict/list
/// structures from Python users without coupling pure-Rust to
/// pyo3.
#[derive(Clone, Debug)]
pub enum BehaviourValue {
    /// 64-bit signed integer.
    Int(i64),
    /// 64-bit float.
    Float(f64),
    /// Boolean.
    Bool(bool),
    /// UTF-8 string.
    String(String),
    /// Raw bytes.
    Bytes(Vec<u8>),
    /// Recursive nested value (used when a Python user puts a
    /// `dict`/`list` into the ctx).
    Json(serde_json::Value),
}

/// Shared key-value context passed to every `Leaf::tick`. Cheap to
/// clone (it is an `Arc`); the inner lock is `parking_lot::RwLock`
/// so concurrent readers do not block each other.
pub type BehaviourCtx = Arc<RwLock<HashMap<String, BehaviourValue>>>;

/// Build an empty context (helper).
pub fn new_ctx() -> BehaviourCtx {
    Arc::new(RwLock::new(HashMap::new()))
}

/// Behaviour-tree tick result.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NodeStatus {
    /// Tick produced no terminal verdict; the runner should tick
    /// the same leaf again on the next sweep.
    Running,
    /// Leaf finished with success.
    Success,
    /// Leaf finished with failure.
    Failure,
}

/// Behaviour-tree leaf trait. Mirrors
/// `python/minecraft_bot/behaviour/nodes.py::BehaviourNode.tick`.
///
/// Filled in by 004 Group I (T072). The full implementation lives
/// in `behaviour::leaves`. This file just nails the trait shape so
/// other modules can depend on it.
#[async_trait::async_trait]
pub trait Leaf: Send + Sync {
    /// Run one tick of the leaf. `bot` is the bot the tree is
    /// driving; `ctx` is the shared key/value store.
    async fn tick(&mut self, bot: &crate::bot::Bot, ctx: &BehaviourCtx) -> NodeStatus;

    /// Reset any internal state (called when a parent restarts the
    /// child after a previous terminal verdict). Default no-op.
    fn reset(&mut self) {}
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ctx_roundtrip_primitives() {
        let ctx = new_ctx();
        {
            let mut w = ctx.write();
            w.insert("i".to_string(), BehaviourValue::Int(42));
            w.insert("f".to_string(), BehaviourValue::Float(2.5));
            w.insert("b".to_string(), BehaviourValue::Bool(true));
            w.insert("s".to_string(), BehaviourValue::String("hi".to_string()));
            w.insert("bytes".to_string(), BehaviourValue::Bytes(vec![1, 2, 3]));
            w.insert(
                "json".to_string(),
                BehaviourValue::Json(serde_json::json!({"nested": [1, 2]})),
            );
        }
        let r = ctx.read();
        assert!(matches!(r.get("i"), Some(BehaviourValue::Int(42))));
        assert!(matches!(r.get("f"), Some(BehaviourValue::Float(_))));
        assert!(matches!(r.get("b"), Some(BehaviourValue::Bool(true))));
    }
}
