//! T016 — Rust live-smoke harness for 004 full Bot parity.
//!
//! This file holds the per-method-group live tests added in 004.
//! Each Phase-3 group lands its own `#[tokio::test]` here (e.g.
//! `test_movement_look_at`, `test_inventory_select_slot`,
//! `test_dig_stone_block`).
//!
//! Runs only under `--features live-smoke`. Bot usernames are taken
//! round-robin from `TestBot1..TestBot9` (op'd on the test arena)
//! to avoid duplicate-login conflicts when tests run in parallel —
//! though the suite still defaults to single-threaded.

#![cfg(feature = "live-smoke")]

use std::env;
use std::sync::atomic::{AtomicUsize, Ordering};

use minecraft_bot::bot::Bot;

/// Pool of usernames op'd on the arena. Round-robin via the
/// `NEXT_USER_IDX` atomic so concurrent tests don't collide.
const TEST_BOT_NAMES: &[&str] = &[
    "TestBot1", "TestBot2", "TestBot3", "TestBot4", "TestBot5", "TestBot6", "TestBot7", "TestBot8",
    "TestBot9",
];

static NEXT_USER_IDX: AtomicUsize = AtomicUsize::new(0);

fn test_host() -> String {
    env::var("MINECRAFT_BOT_TEST_HOST").unwrap_or_else(|_| "172.26.160.1".into())
}

fn test_port() -> u16 {
    env::var("MINECRAFT_BOT_TEST_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(25565)
}

/// Pick the next available test username (round-robin).
fn next_username() -> &'static str {
    let i = NEXT_USER_IDX.fetch_add(1, Ordering::SeqCst) % TEST_BOT_NAMES.len();
    TEST_BOT_NAMES[i]
}

/// Spawn a connected Bot on the live arena. Caller is responsible
/// for `bot.disconnect()` when done.
#[allow(dead_code)]
pub(crate) async fn connect_test_bot() -> Bot {
    let mut bot = Bot::offline(test_host(), test_port(), next_username());
    bot.connect().await.expect("Bot::connect against test arena");
    bot
}

/// Sanity test: harness compiles and the round-robin works.
#[tokio::test]
async fn harness_picks_distinct_usernames() {
    let a = next_username();
    let b = next_username();
    assert_ne!(a, b, "round-robin should hand out two distinct names");
}

// Per-group live tests are appended below by their corresponding
// Phase-3 group landing. Naming convention: `test_<group>_<method>`.

// --- Combined live-smoke (Groups A + B + C) ----------------------------------
//
// Paper rate-limits per-IP reconnects (~3-5s lockout) so we batch all
// the per-method assertions into one bot session per turn. Inside the
// session each method is a tiny block; failure prints which one.

use std::time::Duration;

// --- Group B + C combined (T031, T035) --------------------------------------
//
// Paper rate-limits per-IP reconnects (~3s lockout). Bundling all the
// movement+combat assertions into one connection avoids the throttle.

#[tokio::test]
async fn test_state_movement_and_combat_combined() {
    let mut bot = connect_test_bot().await;

    // --- Group A: state accessors populate from initial state burst ---
    for _ in 0..20 {
        tokio::time::sleep(Duration::from_millis(250)).await;
        if bot.entity_id().await.is_some() && bot.position().await != (0.0, 64.0, 0.5) {
            break;
        }
    }
    assert!(bot.entity_id().await.is_some(), "entity_id from Login");
    let pos = bot.position().await;
    assert_ne!(pos, (0.0, 64.0, 0.5), "position from PlayerPosition");
    let h = bot.health().await;
    assert!(h > 0.0, "health positive after spawn (got {h})");
    let f = bot.food().await;
    assert!(f > 0 && f <= 20, "food 1..20 after spawn (got {f})");
    assert!(bot.game_mode().await.is_some(), "game_mode from Login");
    assert!(bot.world_name().await.is_some(), "world_name from Login");
    assert!(bot.held_slot().await <= 8, "held_slot <= 8");

    // --- look_at ---
    bot.look_at(10005.0, 200.0, 10005.0)
        .await
        .expect("look_at");
    let yaw = bot.yaw().await;
    let pitch = bot.pitch().await;
    assert!(
        (0.0..=360.0).contains(&yaw),
        "yaw should be in 0..360 (got {yaw})"
    );
    assert!(
        (-90.0..=90.0).contains(&pitch),
        "pitch in -90..90 (got {pitch})"
    );

    // --- sneak / sprint toggles ---
    assert!(!bot.is_sneaking().await, "starts not sneaking");
    bot.sneak(true).await.expect("sneak true");
    assert!(bot.is_sneaking().await, "after sneak(true)");
    bot.sneak(false).await.ok();
    assert!(!bot.is_sneaking().await);
    bot.sprint(true).await.expect("sprint true");
    assert!(bot.is_sprinting().await);
    bot.sprint(false).await.ok();

    // --- swing_arm / jump ---
    bot.swing_arm(0).await.expect("swing_arm");
    bot.jump().await.expect("jump");

    // --- combat ---
    bot.use_item(0).await.expect("use_item");
    bot.attack(999_999).await.expect("attack unknown eid");
    bot.interact_entity(999_999, 0)
        .await
        .expect("interact unknown eid");

    // --- Group D: world query (T042) ---
    // Wait a couple of seconds so the chunk cache gets populated.
    tokio::time::sleep(Duration::from_millis(1500)).await;
    let blocks = bot.find_blocks_nearby("minecraft:stone", 16, 32).await;
    // Sanity: arena floor is stone; at minimum some hits expected.
    println!("find_blocks_nearby(stone, 16): {} hits", blocks.len());
    let _scan = bot.scan_volume(2, false).await;
    let (grid, side) = bot.voxel_grid(2).await;
    assert_eq!(side, 5, "voxel_grid side = 2*radius+1");
    assert_eq!(grid.len(), 5 * 5 * 5);
    let chunks = bot.chunks_around(1).await;
    assert!(!chunks.is_empty(), "chunks_around should have ≥1 loaded chunk");
    let (wm, dims) = bot.world_map_3d(2, Some(1)).await;
    assert_eq!(dims, (5, 3, 5));
    assert_eq!(wm.len(), 5 * 3 * 5);
    // Entity tracker isn't wired to dispatcher yet (deferred); just
    // confirm the API returns empty without panic.
    let _ents = bot.nearby_entities(32.0).await;
    let _plrs = bot.nearby_players(32.0).await;
    let _d = bot.distance_to(0).await;
    let _rc = bot.raycast(8.0).await;

    bot.disconnect().await.ok();
}
