//! Block hardness lookup loaded from `protocol-data/v763/blocks.json`.
//! Used by `Bot::dig` for break-time computation.
//!
//! v0.3.1 polish — replaces the MVP fixed 500 ms timeout.

#![allow(dead_code)]

use std::collections::HashMap;
use std::sync::OnceLock;

use serde::Deserialize;

#[derive(Deserialize)]
struct BlockRow {
    id: i32,
    name: String,
    #[serde(default)]
    hardness: f64,
    #[serde(default)]
    diggable: bool,
}

/// Block id -> (name, hardness) lookup.
#[derive(Debug, Default)]
pub struct HardnessTable {
    by_block_id: HashMap<i32, (String, f64, bool)>,
}

impl HardnessTable {
    /// Hardness for a block id (numeric block, not state). Returns
    /// `0.0` for unknown blocks.
    pub fn hardness(&self, block_id: i32) -> f64 {
        self.by_block_id
            .get(&block_id)
            .map(|(_, h, _)| *h)
            .unwrap_or(0.0)
    }

    /// Whether the block is diggable (some blocks like bedrock are not).
    pub fn diggable(&self, block_id: i32) -> bool {
        self.by_block_id
            .get(&block_id)
            .map(|(_, _, d)| *d)
            .unwrap_or(false)
    }

    /// Approximate break time in seconds, hands-only (no tool).
    ///
    /// Mirrors Mojang's wiki formula for a "no-correct-tool" hand
    /// dig: `time = hardness * 5.0` seconds. With the correct tool
    /// this would be `hardness * 1.5 / tool_speed` — that lookup
    /// stays a backlog item.
    pub fn break_time_seconds(&self, block_id: i32) -> f64 {
        let h = self.hardness(block_id);
        if h <= 0.0 {
            return 0.0;
        }
        h * 5.0
    }
}

const BLOCKS_JSON: &str = include_str!("../../../protocol-data/v763/blocks.json");

fn parse_table() -> HardnessTable {
    let rows: Vec<BlockRow> = serde_json::from_str(BLOCKS_JSON)
        .expect("blocks.json must parse as a JSON list");
    let mut by_block_id = HashMap::with_capacity(rows.len());
    for r in rows {
        by_block_id.insert(r.id, (r.name, r.hardness, r.diggable));
    }
    HardnessTable { by_block_id }
}

static TABLE: OnceLock<HardnessTable> = OnceLock::new();

/// Process-wide accessor.
pub fn hardness_table() -> &'static HardnessTable {
    TABLE.get_or_init(parse_table)
}
