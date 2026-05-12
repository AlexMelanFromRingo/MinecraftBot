//! Live smoke: connect a Rust bot to the Paper test server and stay
//! alive for ~20 seconds.
//!
//! Run::
//!
//!     cargo run --example connect_live --release
//!
//! Env::
//!
//!     MINECRAFT_BOT_TEST_HOST=172.26.160.1
//!     MINECRAFT_BOT_TEST_PORT=25565
//!     MINECRAFT_BOT_USER=TestBot1

use std::env;
use std::time::Duration;

use minecraft_bot::Connection;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let host = env::var("MINECRAFT_BOT_TEST_HOST").unwrap_or_else(|_| "172.26.160.1".into());
    let port: u16 = env::var("MINECRAFT_BOT_TEST_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(25565);
    let user = env::var("MINECRAFT_BOT_USER").unwrap_or_else(|_| "TestBot1".into());

    println!("connecting as {} to {}:{}...", user, host, port);
    let mut conn = Connection::offline(host, port, user);
    conn.connect().await?;
    println!(
        "PLAY reached. entity_id={:?}, world={:?}",
        conn.entity_id().await,
        conn.world_name().await
    );

    println!("idling 20 seconds (keep-alive should auto-reply)...");
    for _ in 0..20 {
        tokio::time::sleep(Duration::from_secs(1)).await;
        if !conn.is_connected() {
            println!("decode task exited unexpectedly");
            break;
        }
    }

    conn.disconnect().await?;
    println!("disconnected cleanly");
    Ok(())
}
