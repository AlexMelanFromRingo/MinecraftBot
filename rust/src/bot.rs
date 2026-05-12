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
    unload_chunk::UnloadChunk,
    update_health::UpdateHealth,
};
use crate::world::{decode_chunk, World};

// Clientbound packet IDs we care about in the dispatcher.
const ID_BLOCK_CHANGE: i32 = 0x0A;
const ID_UNLOAD_CHUNK: i32 = 0x1E;
const ID_MAP_CHUNK: i32 = 0x24;
const ID_MULTI_BLOCK_CHANGE: i32 = 0x43;
const ID_UPDATE_HEALTH: i32 = 0x57;

/// Public bot state snapshot fields kept up-to-date by the dispatch
/// task.
#[derive(Default)]
struct BotState {
    health: f32,
    food: i32,
    saturation: f32,
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
    pub async fn connect(&mut self) -> Result<(), ProtocolError> {
        // Subscribe BEFORE connect() — actually connect() spawns the
        // play loop internally; subscription must outlive that, so
        // attach after connection.connect() returns we lose initial
        // packets. To capture from the start, subscribe FIRST, but
        // Connection::subscribe_packets requires connect to have
        // not-yet-started the loop. The current Connection design has
        // run_play_loop spawned inside connect(); the subscriber list
        // is shared by Arc so subscribing after connect() still works
        // for packets that arrive after. Initial Login (play) is
        // dispatched before subscribers exist; play_state is filled
        // synchronously inside Connection::connect.
        self.connection.connect().await?;

        let mut rx = self.connection.subscribe_packets().await;
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
}
