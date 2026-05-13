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

// --- Group A (T027): state accessors ---------------------------------------

use std::time::Duration;

/// After connect + brief idle, every state accessor returns a sane
/// value. We don't compare against the Python ref here (that's the
/// parity test's job); we just confirm the dispatcher actually
/// populates BotState from Login/SetExperience/HeldItemChange.
#[tokio::test]
async fn test_state_accessors() {
    let mut bot = connect_test_bot().await;
    // Idle until the server has sent the initial state burst.
    for _ in 0..20 {
        tokio::time::sleep(Duration::from_millis(250)).await;
        if bot.entity_id().await.is_some() && bot.position().await.is_some() {
            break;
        }
    }
    let eid = bot.entity_id().await;
    assert!(eid.is_some(), "entity_id should land within 5s of connect");

    let pos = bot.position().await;
    assert!(pos.is_some(), "position should land via PlayerPosition");

    let h = bot.health().await;
    assert!(h > 0.0, "health should be positive after spawn (got {h})");

    let f = bot.food().await;
    assert!(f > 0 && f <= 20, "food in 1..20 after spawn (got {f})");

    let gm = bot.game_mode().await;
    assert!(gm.is_some(), "game_mode set by Login");

    let world = bot.world_name().await;
    assert!(world.is_some(), "world_name set by Login");

    // Held slot defaults to 0 unless the server has sent SetHeldItem.
    let slot = bot.held_slot().await;
    assert!(slot <= 8, "held_slot in 0..8 (got {slot})");

    bot.disconnect().await.expect("disconnect");
}
