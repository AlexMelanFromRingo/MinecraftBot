//! High-level task methods for [`Bot`]: dig, eat, follow, say, chat.
//! Mirrors `python/minecraft_bot/bot.py:1346-1565` plus `dig.py`.
//!
//! 004 Group H (T065..T071). MVP: dig/eat/follow send the correct
//! packet sequences; precise timing (block hardness lookup, eat
//! completion handshake) is simplified to fixed delays — sufficient
//! for parity tests and most live cases.

use std::time::{Duration, Instant};

use super::Bot;
use crate::errors::ProtocolError;
use crate::foods::food_table;
use crate::protocol::v763::packets::play::serverbound::block_dig::BlockDig;

const ACTION_START_DIG: i32 = 0;
const ACTION_FINISH_DIG: i32 = 2;

impl Bot {
    /// Break the block at `(x, y, z)`. MVP: start_dig + 500ms wait +
    /// finish_dig. Per spec Q4 the parity test tolerates a +/- 1
    /// tick offset on the finish_dig packet.
    pub async fn dig(
        &self,
        x: i32,
        y: i32,
        z: i32,
        _expected_block: Option<u32>,
    ) -> Result<(), ProtocolError> {
        // Aim at the block so the server accepts the dig.
        self.look_at(x as f64 + 0.5, y as f64 + 0.5, z as f64 + 0.5)
            .await?;

        let location = (x, y, z);

        // start_dig
        self.connection
            .send(&BlockDig {
                status: ACTION_START_DIG,
                location,
                face: 1,
                sequence: 0,
            })
            .await?;
        // Naive break-time: 500 ms. Hardness-based timing is a
        // backlog polish item.
        tokio::time::sleep(Duration::from_millis(500)).await;
        // finish_dig
        self.connection
            .send(&BlockDig {
                status: ACTION_FINISH_DIG,
                location,
                face: 1,
                sequence: 0,
            })
            .await?;
        // Swing arm at the end (Mojang client behaviour).
        self.swing_arm(0).await
    }

    /// Eat the first food item in the hotbar. MVP: select food slot,
    /// send use_item, wait ~1.5s for eating animation, return.
    pub async fn eat(&self, timeout: Duration) -> Result<(), ProtocolError> {
        let foods = food_table();
        // Find a food item in player_slots.
        let mut food_slot: Option<u8> = None;
        {
            let inv = self.inventory.lock().await;
            for (i, s) in inv.player_slots.iter().enumerate() {
                if let Some(item) = s {
                    if foods.get(&item.item_id).is_some()
                        && (36..=44).contains(&i)
                    {
                        food_slot = Some((i - 36) as u8);
                        break;
                    }
                }
            }
        }
        let slot = match food_slot {
            Some(s) => s,
            None => {
                return Err(ProtocolError::DecodeError(
                    "eat: no food in hotbar".into(),
                ));
            }
        };
        self.select_slot(slot).await?;
        self.use_item(0).await?;
        // Eating animation is ~1.6s for most foods. Wait up to `timeout`.
        let dt = timeout.min(Duration::from_millis(1600));
        tokio::time::sleep(dt).await;
        Ok(())
    }

    /// Track entity `eid` keeping `distance` blocks behind it. MVP:
    /// look_at + walk_to in a loop until within range or timeout.
    pub async fn follow(
        &mut self,
        eid: i32,
        distance: f64,
        timeout: Duration,
    ) -> Result<(), ProtocolError> {
        let deadline = Instant::now() + timeout;
        loop {
            if Instant::now() >= deadline {
                return Ok(());
            }
            let target = self.entities_tracker.get(eid);
            let Some(t) = target else {
                tokio::time::sleep(Duration::from_millis(200)).await;
                continue;
            };
            let (bx, _by, bz) = self.position().await;
            let dx = t.x - bx;
            let dz = t.z - bz;
            let dist = (dx * dx + dz * dz).sqrt();
            if dist <= distance {
                return Ok(());
            }
            self.look_at(t.x, t.y, t.z).await?;
            // Walk to a point `distance` blocks short of the target.
            let scale = (dist - distance) / dist;
            let wx = bx + dx * scale;
            let wz = bz + dz * scale;
            // walk_to is bounded by its own internal timeout.
            self.walk_to(wx, t.y, wz, 5.0).await?;
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
    }

    /// Send a chat message.
    pub async fn say(&self, message: &str) -> Result<(), ProtocolError> {
        use crate::protocol::v763::packets::play::serverbound::chat_message::ChatMessage;
        let ts: i64 = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis() as i64)
            .unwrap_or(0);
        self.connection
            .send(&ChatMessage {
                message: message.to_string(),
                timestamp: ts,
                salt: 0,
                signature: None,
                message_count: 0,
                acknowledged: [0, 0, 0],
            })
            .await
    }

    /// Alias for `say` — matches the Python ref's `bot.chat`.
    pub async fn chat(&self, message: &str) -> Result<(), ProtocolError> {
        self.say(message).await
    }
}
