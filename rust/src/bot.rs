//! Top-level [`Bot`] facade — Rust port of `python/minecraft_bot/bot.py`.
//!
//! Composes a [`Connection`] with a [`World`] cache and a packet
//! dispatcher that updates the cache on map_chunk / block_change /
//! unload_chunk events. Higher-level methods (walk_to, observation,
//! drop_held_item, …) land in follow-on tasks.

use std::sync::Arc;

use tokio::sync::Mutex;
use tokio::task::JoinHandle;

use crate::codec::BytesReader;
use crate::connection::Connection;
use crate::effects::StatusEffects;
use crate::errors::ProtocolError;
use crate::protocol::v763::packets::play::clientbound::{
    block_change::BlockChange,
    map_chunk::MapChunk,
    multi_block_change::MultiBlockChange,
    position::Position as CbPosition,
    unload_chunk::UnloadChunk,
    update_health::UpdateHealth,
};
use crate::world::{decode_chunk, World};

// Clientbound packet IDs we care about in the dispatcher.
const ID_BLOCK_CHANGE: i32 = 0x0A;
const ID_UNLOAD_CHUNK: i32 = 0x1E;
const ID_MAP_CHUNK: i32 = 0x24;
const ID_SYNC_PLAYER_POSITION: i32 = 0x3C;
const ID_MULTI_BLOCK_CHANGE: i32 = 0x43;
const ID_UPDATE_HEALTH: i32 = 0x57;

/// Public bot state snapshot fields kept up-to-date by the dispatch
/// task.
#[derive(Default, Debug, Clone, Copy)]
struct BotState {
    health: f32,
    food: i32,
    saturation: f32,
    x: f64,
    y: f64,
    z: f64,
    yaw: f32,
    pitch: f32,
    position_known: bool,
}

/// Top-level bot: owns a Connection, a World, a StatusEffects tracker.
pub struct Bot {
    /// The underlying Connection (login → play → keep-alive loop).
    pub connection: Connection,
    /// In-memory voxel cache updated by the packet dispatcher.
    pub world: Arc<World>,
    /// Status-effect tracker.
    pub effects: Arc<StatusEffects>,
    /// Bot-side mirror of health / food / saturation.
    state: Arc<Mutex<BotState>>,
    /// Background packet dispatcher (started by `connect`).
    dispatcher: Option<JoinHandle<()>>,
}

impl Bot {
    /// Build a Bot configured for offline-mode connection.
    pub fn offline(host: impl Into<String>, port: u16, username: impl Into<String>) -> Self {
        Self {
            connection: Connection::offline(host, port, username),
            world: Arc::new(World::new()),
            effects: Arc::new(StatusEffects::new()),
            state: Arc::new(Mutex::new(BotState::default())),
            dispatcher: None,
        }
    }

    /// Connect the underlying Connection, then start the packet
    /// dispatcher.
    ///
    /// **Subscribe BEFORE connect** so the spawned play loop fans
    /// out from the first packet onward — including the initial
    /// `synchronize_player_position` (id 0x3C) and `login` (id 0x28)
    /// packets. Connection's `pkt_subscribers` is a shared Arc<Vec>
    /// initialised at offline-construction time, so registering a
    /// subscriber before `connect()` is safe.
    pub async fn connect(&mut self) -> Result<(), ProtocolError> {
        let mut rx = self.connection.subscribe_packets().await;
        self.connection.connect().await?;

        let world = Arc::clone(&self.world);
        let effects = Arc::clone(&self.effects);
        let state = Arc::clone(&self.state);

        let handle = tokio::spawn(async move {
            while let Some((id, body)) = rx.recv().await {
                let mut br = BytesReader::new(&body);
                let result: Result<(), ProtocolError> = match id {
                    ID_MAP_CHUNK => {
                        match MapChunk::decode(&mut br) {
                            Ok(pkt) => {
                                let min_y = world.min_y();
                                let sc = world.section_count();
                                match decode_chunk(&pkt.payload, pkt.chunk_x, pkt.chunk_z, min_y, sc) {
                                    Ok(chunk) => {
                                        world.insert_chunk(chunk);
                                        Ok(())
                                    }
                                    Err(e) => Err(e),
                                }
                            }
                            Err(e) => Err(e),
                        }
                    }
                    ID_UNLOAD_CHUNK => {
                        match UnloadChunk::decode(&mut br) {
                            Ok(pkt) => {
                                world.unload_chunk(pkt.chunk_x, pkt.chunk_z);
                                Ok(())
                            }
                            Err(e) => Err(e),
                        }
                    }
                    ID_BLOCK_CHANGE => {
                        if let Ok(pkt) = BlockChange::decode(&mut br) {
                            let (x, y, z) = pkt.location;
                            world.set_block(x, y, z, pkt.block_state_id);
                        }
                        Ok(())
                    }
                    ID_MULTI_BLOCK_CHANGE => {
                        if let Ok(pkt) = MultiBlockChange::decode(&mut br) {
                            let cx = pkt.chunk_section_x;
                            let cz = pkt.chunk_section_z;
                            let sy = pkt.chunk_section_y;
                            let base_y = sy * 16;
                            for rec in &pkt.records {
                                let state_id = (*rec >> 12) as i32;
                                let rel = (*rec & 0xFFF) as i32;
                                let lx = (rel >> 8) & 0xF;
                                let lz = (rel >> 4) & 0xF;
                                let ly = rel & 0xF;
                                let wx = cx * 16 + lx;
                                let wz = cz * 16 + lz;
                                let wy = base_y + ly;
                                world.set_block(wx, wy, wz, state_id);
                            }
                        }
                        Ok(())
                    }
                    ID_UPDATE_HEALTH => {
                        if let Ok(pkt) = UpdateHealth::decode(&mut br) {
                            let mut s = state.lock().await;
                            s.health = pkt.health;
                            s.food = pkt.food;
                            s.saturation = pkt.food_saturation;
                        }
                        Ok(())
                    }
                    ID_SYNC_PLAYER_POSITION => {
                        if let Ok(pkt) = CbPosition::decode(&mut br) {
                            // Flags bits: 0x01=x rel, 0x02=y rel, 0x04=z rel,
                            // 0x08=yaw rel, 0x10=pitch rel. Treat absolute
                            // values by default; relative requires prior
                            // tracked position. For first packet (no prior)
                            // treat as absolute regardless of flag bits.
                            let mut s = state.lock().await;
                            let rel = pkt.flags as i32;
                            let prior_known = s.position_known;
                            s.x = if prior_known && (rel & 0x01) != 0 { s.x + pkt.x } else { pkt.x };
                            s.y = if prior_known && (rel & 0x02) != 0 { s.y + pkt.y } else { pkt.y };
                            s.z = if prior_known && (rel & 0x04) != 0 { s.z + pkt.z } else { pkt.z };
                            s.yaw = if prior_known && (rel & 0x08) != 0 { s.yaw + pkt.yaw } else { pkt.yaw };
                            s.pitch = if prior_known && (rel & 0x10) != 0 { s.pitch + pkt.pitch } else { pkt.pitch };
                            s.position_known = true;
                        }
                        Ok(())
                    }
                    _ => Ok(()),
                };
                // Errors in the dispatcher are non-fatal; log via eprintln
                // for now. A future hooks layer will surface them.
                if let Err(e) = result {
                    eprintln!("[bot dispatcher] packet 0x{id:X}: {e}");
                }
                // effects is updated by entity_effect / remove_entity_effect
                // packets which aren't dispatched here yet; keep arc alive.
                let _ = &effects;
            }
        });
        self.dispatcher = Some(handle);
        Ok(())
    }

    /// Disconnect the underlying Connection and stop the dispatcher.
    pub async fn disconnect(&mut self) -> Result<(), ProtocolError> {
        if let Some(h) = self.dispatcher.take() {
            h.abort();
        }
        self.connection.disconnect().await
    }

    /// Bot's entity-id (from the play `Login` packet).
    pub async fn entity_id(&self) -> Option<i32> {
        self.connection.entity_id().await
    }

    /// Bot's last-known health.
    pub async fn health(&self) -> f32 {
        self.state.lock().await.health
    }

    /// Bot's last-known food.
    pub async fn food(&self) -> i32 {
        self.state.lock().await.food
    }

    /// Bot's last-known position `(x, y, z, yaw, pitch)`. Returns
    /// `None` until the server has sent at least one
    /// `synchronize_player_position` packet.
    pub async fn position(&self) -> Option<(f64, f64, f64, f32, f32)> {
        let s = *self.state.lock().await;
        if s.position_known {
            Some((s.x, s.y, s.z, s.yaw, s.pitch))
        } else {
            None
        }
    }
}
