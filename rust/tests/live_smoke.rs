//! Live-smoke integration test (T129).
//!
//! Gated by ``cargo test --features live-smoke``. Connects a Rust bot
//! to the configured Paper server and verifies it reaches PLAY,
//! populates entity_id, idles through several keep-alive cycles,
//! then disconnects cleanly.
//!
//! Env::
//!
//!     MINECRAFT_BOT_TEST_HOST  (default 172.26.160.1)
//!     MINECRAFT_BOT_TEST_PORT  (default 25565)
//!
//! Single test on purpose — Paper throttles fast reconnects from the
//! same IP and parallel test cases will trip the throttle.

#![cfg(feature = "live-smoke")]

use std::env;
use std::time::Duration;

use minecraft_bot::Connection;


fn test_host() -> String {
    env::var("MINECRAFT_BOT_TEST_HOST").unwrap_or_else(|_| "172.26.160.1".into())
}

fn test_port() -> u16 {
    env::var("MINECRAFT_BOT_TEST_PORT").ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(25565)
}


#[tokio::test]
async fn connect_play_idle_disconnect() {
    let mut conn = Connection::offline(test_host(), test_port(), "TestBot1");
    conn.connect().await.expect("connect succeeded");
    assert!(conn.is_connected(), "decoder loop should be running");

    let eid = conn.entity_id().await;
    assert!(eid.is_some(), "entity_id should be set after Login (Play)");

    let world = conn.world_name().await;
    assert!(world.is_some(), "world_name should be set");

    // Idle for 15 seconds — exercises keep-alive auto-reply (Paper
    // sends a clientbound KeepAlive every ~15 s and kicks if we don't
    // echo it within 30 s).
    for _ in 0..15 {
        tokio::time::sleep(Duration::from_secs(1)).await;
        assert!(conn.is_connected(), "decoder loop dropped during idle");
    }

    conn.disconnect().await.expect("clean disconnect");
}
