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
        // Hardness-based break-time (v0.3.1). Look up the block's
        // hardness via the World cache and the hardness table.
        let block_id = self.world.query_guard().get_block_id(x, y, z);
        // block_table maps state -> block; for hand-only digging the
        // formula is `hardness * 5.0` seconds (Mojang wiki). Add a
        // small safety margin so finish_dig isn't sent before the
        // server has registered the break.
        let secs = crate::world::hardness::hardness_table().break_time_seconds(block_id);
        // Clamp to a sensible minimum (50 ms for instant-break
        // blocks) and maximum (5 s — anything slower means the wrong
        // tool, fall back to retry-on-next-call).
        let secs = secs.clamp(0.05, 5.0);
        tokio::time::sleep(Duration::from_secs_f64(secs)).await;
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

    /// Eat the first food item in the hotbar. v0.3.1: subscribe to
    /// `EntityStatus(status=9)` (player finished using item) via
    /// the packet-hook mechanism, send `use_item`, await the status,
    /// fall back to the timeout if the server is slow.
    pub async fn eat(&self, timeout: Duration) -> Result<(), ProtocolError> {
        let foods = food_table();
        let mut food_slot: Option<u8> = None;
        {
            let inv = self.inventory.lock().await;
            for (i, s) in inv.player_slots.iter().enumerate() {
                if let Some(item) = s {
                    if foods.get(&item.item_id).is_some() && (36..=44).contains(&i) {
                        food_slot = Some((i - 36) as u8);
                        break;
                    }
                }
            }
        }
        let slot = match food_slot {
            Some(s) => s,
            None => {
                return Err(ProtocolError::DecodeError("eat: no food in hotbar".into()));
            }
        };
        let bot_eid = self.state.lock().await.entity_id.unwrap_or(0);
        self.select_slot(slot).await?;

        // Register EntityStatus listener before sending use_item.
        let (tx, rx) = tokio::sync::oneshot::channel::<()>();
        let tx_arc = std::sync::Arc::new(std::sync::Mutex::new(Some(tx)));
        let tx_clone = tx_arc.clone();
        self.on_packet(
            0x1C,
            Box::new(move |_id, body| {
                // EntityStatus body: VarInt(entity_id), i8(status).
                let mut val: i32 = 0;
                let mut bits = 0;
                let mut idx = 0;
                while idx < 5.min(body.len()) {
                    let b = body[idx];
                    val |= ((b & 0x7F) as i32) << bits;
                    idx += 1;
                    if (b & 0x80) == 0 {
                        break;
                    }
                    bits += 7;
                }
                if val != bot_eid || idx >= body.len() {
                    return;
                }
                let status = body[idx] as i8;
                // Mojang status code 9 = "player finished using item".
                if status == 9 {
                    if let Ok(mut g) = tx_clone.lock() {
                        if let Some(tx) = g.take() {
                            let _ = tx.send(());
                        }
                    }
                }
            }),
        )
        .await;

        self.use_item(0).await?;
        // Await EntityStatus(9) or fall back to `timeout`.
        let _ = tokio::time::timeout(timeout, rx).await;
        Ok(())
    }

    /// Track entity `eid` keeping `distance` blocks behind it.
    ///
    /// v0.3.1 polish — path re-planning: re-evaluate the target's
    /// position before every `walk_to` and abort the in-flight walk
    /// early if the target has moved more than `re_path_radius`
    /// blocks since the last plan.
    pub async fn follow(
        &mut self,
        eid: i32,
        distance: f64,
        timeout: Duration,
    ) -> Result<(), ProtocolError> {
        let deadline = Instant::now() + timeout;
        const RE_PATH_RADIUS: f64 = 2.0;
        let mut last_target_xz: Option<(f64, f64)> = None;
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
            // Re-plan only if the target has moved meaningfully since
            // the previous plan — otherwise the current walk_to
            // already heads toward roughly the right point.
            let should_replan = match last_target_xz {
                Some((lx, lz)) => {
                    let dxp = t.x - lx;
                    let dzp = t.z - lz;
                    (dxp * dxp + dzp * dzp).sqrt() > RE_PATH_RADIUS
                }
                None => true,
            };
            if should_replan {
                self.look_at(t.x, t.y, t.z).await?;
                let scale = (dist - distance) / dist;
                let wx = bx + dx * scale;
                let wz = bz + dz * scale;
                self.walk_to(wx, t.y, wz, 5.0).await?;
                last_target_xz = Some((t.x, t.z));
            } else {
                tokio::time::sleep(Duration::from_millis(200)).await;
            }
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
