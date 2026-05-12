//! Block-state classification table — Rust port of
//! `python/minecraft_bot/world/block_table.py`.
//!
//! Loads `protocol-data/v763/block_states.json` on first call and
//! exposes the same classification predicates the Python reference
//! uses (`is_solid`, `is_water`, `is_lava`, `is_navigable_obstacle`,
//! `is_passthrough`, `step_height`).

use std::collections::{HashMap, HashSet};
use std::sync::OnceLock;

use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct BlockInfo {
    #[allow(dead_code)]
    id: i32,
    #[allow(dead_code)]
    default_state: Option<i32>,
    #[allow(dead_code)]
    min_state: Option<i32>,
    #[allow(dead_code)]
    max_state: Option<i32>,
    #[serde(default)]
    transparent: bool,
    #[serde(default)]
    #[allow(dead_code)]
    diggable: bool,
    #[serde(default)]
    #[allow(dead_code)]
    material: Option<String>,
    #[serde(default)]
    #[allow(dead_code)]
    stack_size: Option<i32>,
}

#[derive(Debug, Deserialize)]
struct RawTable {
    state_to_block: HashMap<String, String>,
    block_table: HashMap<String, BlockInfo>,
}

struct Loaded {
    state_to_block: HashMap<i32, String>,
    block_table: HashMap<String, BlockInfo>,
}

const RAW_JSON: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../protocol-data/v763/block_states.json"
));

fn loaded() -> &'static Loaded {
    static CACHED: OnceLock<Loaded> = OnceLock::new();
    CACHED.get_or_init(|| {
        let parsed: RawTable =
            serde_json::from_str(RAW_JSON).expect("failed to parse block_states.json");
        let state_to_block: HashMap<i32, String> = parsed
            .state_to_block
            .into_iter()
            .map(|(k, v)| (k.parse::<i32>().unwrap_or(0), v))
            .collect();
        Loaded {
            state_to_block,
            block_table: parsed.block_table,
        }
    })
}

/// Block name (`"minecraft:stone"`) for `state_id`, or `None` if the
/// state is unknown.
pub fn get_name(state_id: i32) -> Option<&'static str> {
    loaded().state_to_block.get(&state_id).map(String::as_str)
}

/// Block-level metadata for the block of `state_id`, or `None`.
pub fn get_block_info(state_id: i32) -> Option<&'static BlockInfo> {
    let name = get_name(state_id)?;
    loaded().block_table.get(name)
}

fn block_info_by_name(name: &str) -> Option<&'static BlockInfo> {
    loaded().block_table.get(name)
}

// ---- Passthrough / obstacle classifications ------------------------------

fn passthrough_names() -> &'static HashSet<&'static str> {
    static CACHED: OnceLock<HashSet<&'static str>> = OnceLock::new();
    CACHED.get_or_init(|| {
        [
            "minecraft:air",
            "minecraft:cave_air",
            "minecraft:void_air",
            "minecraft:water",
            "minecraft:lava",
            "minecraft:bubble_column",
            "minecraft:grass",
            "minecraft:tall_grass",
            "minecraft:fern",
            "minecraft:large_fern",
            "minecraft:dead_bush",
            "minecraft:seagrass",
            "minecraft:tall_seagrass",
            "minecraft:kelp",
            "minecraft:kelp_plant",
            "minecraft:dandelion",
            "minecraft:poppy",
            "minecraft:blue_orchid",
            "minecraft:allium",
            "minecraft:azure_bluet",
            "minecraft:red_tulip",
            "minecraft:orange_tulip",
            "minecraft:white_tulip",
            "minecraft:pink_tulip",
            "minecraft:oxeye_daisy",
            "minecraft:cornflower",
            "minecraft:lily_of_the_valley",
            "minecraft:wither_rose",
            "minecraft:sunflower",
            "minecraft:lilac",
            "minecraft:rose_bush",
            "minecraft:peony",
            "minecraft:torchflower",
            "minecraft:pitcher_plant",
            "minecraft:torch",
            "minecraft:wall_torch",
            "minecraft:soul_torch",
            "minecraft:soul_wall_torch",
            "minecraft:redstone_torch",
            "minecraft:redstone_wall_torch",
            "minecraft:ladder",
            "minecraft:vine",
            "minecraft:rail",
            "minecraft:powered_rail",
            "minecraft:detector_rail",
            "minecraft:activator_rail",
            "minecraft:cobweb",
            "minecraft:lever",
            "minecraft:tripwire",
            "minecraft:tripwire_hook",
            "minecraft:scaffolding",
            // 1-2 layer snow heuristic — see Python comment.
            "minecraft:snow",
        ]
        .into_iter()
        .collect()
    })
}

const OBSTACLE_PREFIXES: &[&str] = &[
    "minecraft:oak_door",
    "minecraft:spruce_door",
    "minecraft:birch_door",
    "minecraft:jungle_door",
    "minecraft:acacia_door",
    "minecraft:dark_oak_door",
    "minecraft:mangrove_door",
    "minecraft:cherry_door",
    "minecraft:bamboo_door",
    "minecraft:crimson_door",
    "minecraft:warped_door",
    "minecraft:iron_door",
    "minecraft:oak_fence_gate",
    "minecraft:spruce_fence_gate",
    "minecraft:birch_fence_gate",
    "minecraft:jungle_fence_gate",
    "minecraft:acacia_fence_gate",
    "minecraft:dark_oak_fence_gate",
    "minecraft:mangrove_fence_gate",
    "minecraft:cherry_fence_gate",
    "minecraft:bamboo_fence_gate",
    "minecraft:crimson_fence_gate",
    "minecraft:warped_fence_gate",
    "minecraft:oak_trapdoor",
    "minecraft:spruce_trapdoor",
    "minecraft:birch_trapdoor",
    "minecraft:jungle_trapdoor",
    "minecraft:acacia_trapdoor",
    "minecraft:dark_oak_trapdoor",
    "minecraft:mangrove_trapdoor",
    "minecraft:cherry_trapdoor",
    "minecraft:bamboo_trapdoor",
    "minecraft:crimson_trapdoor",
    "minecraft:warped_trapdoor",
    "minecraft:iron_trapdoor",
];

fn starts_with_obstacle_prefix(name: &str) -> bool {
    OBSTACLE_PREFIXES.iter().any(|p| name.starts_with(p))
}

/// Full-cube solid (pathfinder cannot pass through).
pub fn is_solid(state_id: i32) -> bool {
    let Some(name) = get_name(state_id) else {
        return false;
    };
    if passthrough_names().contains(name) {
        return false;
    }
    if starts_with_obstacle_prefix(name) {
        return false;
    }
    let Some(info) = block_info_by_name(name) else {
        return false;
    };
    if info.transparent {
        // Glass, leaves, ice are transparent-but-solid.
        return name.contains("leaves") || name.contains("glass") || name.contains("ice");
    }
    true
}

/// Water source / flowing water / bubble column.
pub fn is_water(state_id: i32) -> bool {
    matches!(
        get_name(state_id),
        Some("minecraft:water") | Some("minecraft:bubble_column")
    )
}

/// Lava (source or flowing).
pub fn is_lava(state_id: i32) -> bool {
    get_name(state_id) == Some("minecraft:lava")
}

/// Door / fence gate / trapdoor — pathfinder may cross with a small
/// extra cost; physics tick auto-opens during traversal.
pub fn is_navigable_obstacle(state_id: i32) -> bool {
    match get_name(state_id) {
        Some(n) => starts_with_obstacle_prefix(n),
        None => false,
    }
}

/// True if the bot can walk through this block without any obstacle
/// handling (air, grass, water, torches, …).
pub fn is_passthrough(state_id: i32) -> bool {
    match get_name(state_id) {
        Some(n) => passthrough_names().contains(n),
        None => false,
    }
}

/// Effective top-Y for physics step-up.
pub fn step_height(state_id: i32) -> f64 {
    if !is_solid(state_id) {
        return 0.0;
    }
    let Some(name) = get_name(state_id) else {
        return 0.0;
    };
    if name.ends_with("_slab") {
        return 0.5;
    }
    if name.ends_with("_stairs") {
        return 0.5;
    }
    1.0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn air_is_passthrough_not_solid() {
        // state_id 0 = minecraft:air.
        assert_eq!(get_name(0), Some("minecraft:air"));
        assert!(!is_solid(0));
        assert!(is_passthrough(0));
    }

    #[test]
    fn stone_is_solid() {
        // state_id 1 = minecraft:stone.
        assert_eq!(get_name(1), Some("minecraft:stone"));
        assert!(is_solid(1));
        assert!(!is_passthrough(1));
        assert_eq!(step_height(1), 1.0);
    }

    #[test]
    fn water_classification() {
        // Pick a known water state_id from the table.
        // The water source block has multiple states for levels 0..15.
        // Find one via the registry.
        for (sid, name) in &loaded().state_to_block {
            if name == "minecraft:water" {
                assert!(is_water(*sid));
                assert!(!is_solid(*sid));
                return;
            }
        }
        panic!("no water state found in block_states.json");
    }

    #[test]
    fn unknown_state_safe_defaults() {
        assert_eq!(get_name(999_999), None);
        assert!(!is_solid(999_999));
        assert!(!is_water(999_999));
        assert!(!is_passthrough(999_999));
        assert_eq!(step_height(999_999), 0.0);
    }
}
