//! T038 live smoke — Bot connects, dispatcher fills World cache.
//!
//! Connects to Paper, idles for 5 seconds, and verifies at least one
//! chunk was loaded into the World cache by the packet dispatcher.

#![cfg(feature = "live-smoke")]

use std::env;
use std::time::Duration;

use minecraft_bot::bot::Bot;

fn test_host() -> String {
    env::var("MINECRAFT_BOT_TEST_HOST").unwrap_or_else(|_| "172.26.160.1".into())
}

fn test_port() -> u16 {
    env::var("MINECRAFT_BOT_TEST_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(25565)
}

#[tokio::test]
async fn bot_connects_and_fills_world_cache() {
    let mut bot = Bot::offline(test_host(), test_port(), "TestBot2");
    bot.connect().await.expect("Bot::connect");
    assert!(bot.connection.is_connected(), "Connection should be active");

    // Idle for a few seconds — server streams chunks during this.
    for _ in 0..10 {
        tokio::time::sleep(Duration::from_millis(500)).await;
        if bot.world.loaded_chunk_count() > 0 {
            break;
        }
    }
    let loaded = bot.world.loaded_chunk_count();
    assert!(
        loaded > 0,
        "expected at least one chunk loaded into World after 5s; got {loaded}"
    );
    eprintln!("[bot_live] {} chunks loaded into world cache", loaded);

    bot.disconnect().await.expect("disconnect");
}
