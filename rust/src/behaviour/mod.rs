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

use std::sync::Arc;
use std::time::Duration;

use crate::bot::Bot;

/// Behaviour-tree control node: Selector. Ticks children in order;
/// returns Success on the first Success, Failure if all Failure.
pub struct Selector {
    children: Vec<Box<dyn Leaf>>,
    current: usize,
}

impl Selector {
    /// New selector with given children.
    pub fn new(children: Vec<Box<dyn Leaf>>) -> Self {
        Self {
            children,
            current: 0,
        }
    }
}

#[async_trait::async_trait]
impl Leaf for Selector {
    async fn tick(&mut self, bot: &Bot, ctx: &BehaviourCtx) -> NodeStatus {
        while self.current < self.children.len() {
            let status = self.children[self.current].tick(bot, ctx).await;
            match status {
                NodeStatus::Success => {
                    self.current = 0;
                    return NodeStatus::Success;
                }
                NodeStatus::Running => return NodeStatus::Running,
                NodeStatus::Failure => self.current += 1,
            }
        }
        self.current = 0;
        NodeStatus::Failure
    }

    fn reset(&mut self) {
        self.current = 0;
        for c in &mut self.children {
            c.reset();
        }
    }
}

/// Sequencer: ticks children in order; Failure on first Failure,
/// Success when all Success.
pub struct Sequencer {
    children: Vec<Box<dyn Leaf>>,
    current: usize,
}

impl Sequencer {
    /// New sequencer.
    pub fn new(children: Vec<Box<dyn Leaf>>) -> Self {
        Self {
            children,
            current: 0,
        }
    }
}

#[async_trait::async_trait]
impl Leaf for Sequencer {
    async fn tick(&mut self, bot: &Bot, ctx: &BehaviourCtx) -> NodeStatus {
        while self.current < self.children.len() {
            let status = self.children[self.current].tick(bot, ctx).await;
            match status {
                NodeStatus::Failure => {
                    self.current = 0;
                    return NodeStatus::Failure;
                }
                NodeStatus::Running => return NodeStatus::Running,
                NodeStatus::Success => self.current += 1,
            }
        }
        self.current = 0;
        NodeStatus::Success
    }

    fn reset(&mut self) {
        self.current = 0;
        for c in &mut self.children {
            c.reset();
        }
    }
}

/// Inverter: inverts the child's Success/Failure verdict; passes
/// Running through.
pub struct Inverter {
    child: Box<dyn Leaf>,
}

impl Inverter {
    /// New inverter over `child`.
    pub fn new(child: Box<dyn Leaf>) -> Self {
        Self { child }
    }
}

#[async_trait::async_trait]
impl Leaf for Inverter {
    async fn tick(&mut self, bot: &Bot, ctx: &BehaviourCtx) -> NodeStatus {
        match self.child.tick(bot, ctx).await {
            NodeStatus::Success => NodeStatus::Failure,
            NodeStatus::Failure => NodeStatus::Success,
            NodeStatus::Running => NodeStatus::Running,
        }
    }
    fn reset(&mut self) {
        self.child.reset();
    }
}

/// Repeater: ticks the child up to `max_count` times, returning
/// Success when exhausted. `None` means repeat forever.
pub struct Repeater {
    child: Box<dyn Leaf>,
    max_count: Option<u32>,
    count: u32,
}

impl Repeater {
    /// New repeater. `max_count = None` means infinite.
    pub fn new(child: Box<dyn Leaf>, max_count: Option<u32>) -> Self {
        Self {
            child,
            max_count,
            count: 0,
        }
    }
}

#[async_trait::async_trait]
impl Leaf for Repeater {
    async fn tick(&mut self, bot: &Bot, ctx: &BehaviourCtx) -> NodeStatus {
        if let Some(m) = self.max_count {
            if self.count >= m {
                return NodeStatus::Success;
            }
        }
        let status = self.child.tick(bot, ctx).await;
        match status {
            NodeStatus::Success | NodeStatus::Failure => {
                self.count += 1;
                self.child.reset();
                NodeStatus::Running
            }
            NodeStatus::Running => NodeStatus::Running,
        }
    }
    fn reset(&mut self) {
        self.count = 0;
        self.child.reset();
    }
}

/// Top-level driver for running a tree on a Bot.
pub struct BehaviourRunner {
    /// How long to sleep between ticks.
    pub tick_dt: Duration,
    cancel: Arc<tokio::sync::Notify>,
}

impl BehaviourRunner {
    /// New runner with a 500 ms default tick.
    pub fn new() -> Self {
        Self {
            tick_dt: Duration::from_millis(500),
            cancel: Arc::new(tokio::sync::Notify::new()),
        }
    }

    /// Run `root` against `bot` until it terminates (Success or
    /// Failure), `max_ticks` is reached, or `cancel()` is called.
    pub async fn run(
        &self,
        root: &mut dyn Leaf,
        bot: &Bot,
        ctx: BehaviourCtx,
        max_ticks: Option<u32>,
    ) -> NodeStatus {
        let mut ticks = 0u32;
        loop {
            if let Some(max) = max_ticks {
                if ticks >= max {
                    return NodeStatus::Failure;
                }
            }
            ticks += 1;
            let status = root.tick(bot, &ctx).await;
            if !matches!(status, NodeStatus::Running) {
                return status;
            }
            tokio::select! {
                _ = tokio::time::sleep(self.tick_dt) => {}
                _ = self.cancel.notified() => return NodeStatus::Failure,
            }
        }
    }

    /// Signal the running tree to stop on the next sleep boundary.
    pub fn cancel(&self) {
        self.cancel.notify_waiters();
    }
}

impl Default for BehaviourRunner {
    fn default() -> Self {
        Self::new()
    }
}
