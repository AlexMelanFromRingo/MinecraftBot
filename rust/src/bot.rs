//! Top-level [`Bot`] facade — Rust port of `python/minecraft_bot/bot.py`.
//!
//! Composes a [`Connection`] with a [`World`] cache and a packet
//! dispatcher that updates the cache on map_chunk / block_change /
//! unload_chunk events. Higher-level methods (walk_to, observation,
//! drop_held_item, …) land in follow-on tasks.
//!
//! 004 split: this file owns the `Bot` struct, the dispatcher, and the
//! 13 methods that shipped in 003. Methods added in 004 live in the
//! per-group sub-modules under `bot/` (see [`state`], [`movement`],
//! [`combat`], [`world_query`], [`inventory`], [`containers`],
//! [`tasks`]). Each sub-module adds `impl Bot` blocks; the type
//! definition itself stays here so all sub-modules can `use super::Bot`.

pub mod combat;
pub mod containers;
pub mod inventory;
pub mod movement;
pub mod state;
pub mod tasks;
pub mod world_query;

use std::collections::HashMap;
use std::sync::Arc;

use tokio::sync::Mutex;
use tokio::task::JoinHandle;

use std::time::Duration;

use crate::codec::BytesReader;
use crate::connection::Connection;
use crate::effects::StatusEffects;
use crate::errors::ProtocolError;
use crate::pathfinding::{find_path, Pos};
use crate::physics::{self as rphys, PhysicsIntent, PhysicsState};
use crate::protocol::v763::packets::play::clientbound::{
    block_change::BlockChange, map_chunk::MapChunk, multi_block_change::MultiBlockChange,
    position::Position as CbPosition, unload_chunk::UnloadChunk, update_health::UpdateHealth,
};
use crate::protocol::v763::packets::play::serverbound::block_dig::BlockDig;
use crate::protocol::v763::packets::play::serverbound::position::Position as SbPosition;
use crate::world::block_table;
use crate::world::{decode_chunk, World};

// BlockDig "status" code values (1.20.1, Player Action enum).
const ACTION_DROP_ITEM: i32 = 3;
const ACTION_DROP_STACK: i32 = 4;

/// Per-tick cap for the **diagnostic** `walk_to_blind` slider only.
/// The production [`Bot::walk_to`] drives motion through
/// `physics::tick` instead, which produces vanilla 0.21-blocks/tick
/// sub-steps and never needs an explicit anti-cheat cap. This 2-block
/// budget gives `walk_to_blind` plenty of margin under Paper's
/// `delta² > 100` ⇒ ~10 blocks/tick "moved too quickly" gate.
const MAX_PREDICTION_RADIUS: f64 = 2.0;

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

/// User-supplied callback for a packet hook. Takes the packet id
/// and raw body bytes (after the packet-id varint, before any auto
/// keep-alive / teleport-confirm handling) and returns any future
/// work. The dispatcher invokes hooks on its own task; long-running
/// hooks should spawn their own task to avoid blocking the loop.
pub type PacketHook = Box<dyn Fn(i32, &[u8]) + Send + Sync + 'static>;

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
    /// User-registered packet hooks keyed by packet id. Hooks run
    /// inside the dispatcher task after the built-in world / state
    /// updates, before the auto keep-alive handler in `Connection`.
    hooks: Arc<Mutex<HashMap<i32, Vec<PacketHook>>>>,
    /// Inventory tracker — populated by the dispatcher from SetSlot /
    /// WindowItems / OpenScreen / CloseWindow packets. Behind the
    /// dedicated `inventory_lock` mutex so concurrent inventory
    /// mutations from user-side code serialise per spec R-2.
    pub(crate) inventory: Arc<Mutex<crate::bot::inventory::InventoryState>>,
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
            hooks: Arc::new(Mutex::new(HashMap::new())),
            inventory: Arc::new(Mutex::new(crate::bot::inventory::InventoryState::new())),
        }
    }

    /// Acquire the inventory mutex and run `f` against the locked
    /// `InventoryState`. See research.md R-2: only inventory-mutating
    /// methods (click_slot, move_item, drop_item, equip_armor, etc.)
    /// acquire this lock; movement and queries stay parallel.
    pub async fn with_inventory_lock<F, R>(&self, f: F) -> R
    where
        F: for<'a> FnOnce(&'a mut crate::bot::inventory::InventoryState) -> R,
    {
        let mut guard = self.inventory.lock().await;
        f(&mut *guard)
    }

    /// Register a callback for a clientbound packet id. Multiple
    /// callbacks per id are allowed; they fire in registration order.
    /// Hooks receive the packet body (after the id varint).
    pub async fn on_packet(&self, packet_id: i32, callback: PacketHook) {
        let mut hooks = self.hooks.lock().await;
        hooks.entry(packet_id).or_default().push(callback);
    }

    /// Drop every registered hook.
    pub async fn clear_hooks(&self) {
        self.hooks.lock().await.clear();
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
        let hooks = Arc::clone(&self.hooks);

        let handle = tokio::spawn(async move {
            while let Some((id, body)) = rx.recv().await {
                // User-registered hooks first — they see every packet
                // including ones the built-in handlers below don't
                // touch. Keep the hooks map locked briefly to avoid
                // blocking unrelated `on_packet` calls.
                {
                    let hooks_g = hooks.lock().await;
                    if let Some(cbs) = hooks_g.get(&id) {
                        for cb in cbs {
                            cb(id, &body);
                        }
                    }
                }
                let mut br = BytesReader::new(&body);
                let result: Result<(), ProtocolError> = match id {
                    ID_MAP_CHUNK => match MapChunk::decode(&mut br) {
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
                    },
                    ID_UNLOAD_CHUNK => match UnloadChunk::decode(&mut br) {
                        Ok(pkt) => {
                            world.unload_chunk(pkt.chunk_x, pkt.chunk_z);
                            Ok(())
                        }
                        Err(e) => Err(e),
                    },
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
                            s.x = if prior_known && (rel & 0x01) != 0 {
                                s.x + pkt.x
                            } else {
                                pkt.x
                            };
                            s.y = if prior_known && (rel & 0x02) != 0 {
                                s.y + pkt.y
                            } else {
                                pkt.y
                            };
                            s.z = if prior_known && (rel & 0x04) != 0 {
                                s.z + pkt.z
                            } else {
                                pkt.z
                            };
                            s.yaw = if prior_known && (rel & 0x08) != 0 {
                                s.yaw + pkt.yaw
                            } else {
                                pkt.yaw
                            };
                            s.pitch = if prior_known && (rel & 0x10) != 0 {
                                s.pitch + pkt.pitch
                            } else {
                                pkt.pitch
                            };
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

    /// Drop the currently-held item via a `BlockDig` Player Action.
    /// When `full_stack` is true the entire stack is dropped (vanilla
    /// shift-Q behaviour); otherwise a single item is dropped (Q).
    pub async fn drop_held_item(&self, full_stack: bool) -> Result<(), ProtocolError> {
        let status = if full_stack {
            ACTION_DROP_STACK
        } else {
            ACTION_DROP_ITEM
        };
        let pkt = BlockDig {
            status,
            location: (0, 0, 0),
            face: 0,
            sequence: 0,
        };
        self.connection.send(&pkt).await
    }

    /// Send already-encoded packet bytes through the connection's
    /// framer. The caller is responsible for prepending the packet-ID
    /// varint to `payload` (matching the serverbound wire format).
    ///
    /// This is the "escape hatch" path that lets callers send any of
    /// the 176 protocol packets without needing a per-packet PyO3
    /// wrapper: encode via the Python reference's typed dataclass,
    /// hand the resulting bytes to this method.
    pub async fn send_raw(&self, payload: &[u8]) -> Result<(), ProtocolError> {
        self.connection.send_raw(payload).await
    }

    /// **Diagnostic / blind walk** — no path planning, no collision.
    /// Just slides the bot's position toward `(tx, ty, tz)` at 20 Hz,
    /// capped at 5 blocks per tick. Useful for testing the
    /// position-send loop in isolation from the pathfinder.
    pub async fn walk_to_blind(
        &self,
        tx: f64,
        ty: f64,
        tz: f64,
        timeout_secs: f64,
    ) -> Result<bool, ProtocolError> {
        // Wait for initial position from the server.
        let deadline = tokio::time::Instant::now() + Duration::from_secs_f64(timeout_secs);
        for _ in 0..40 {
            if self.state.lock().await.position_known {
                break;
            }
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
        let (mut local_x, mut local_y, mut local_z) = {
            let s = self.state.lock().await;
            if !s.position_known {
                return Err(ProtocolError::DecodeError(
                    "walk_to_blind: no position arrived within 4s".into(),
                ));
            }
            (s.x, s.y, s.z)
        };
        loop {
            if tokio::time::Instant::now() > deadline {
                return Ok(false);
            }
            // Re-sync from dispatcher on drift.
            {
                let s = self.state.lock().await;
                let dsx = s.x - local_x;
                let dsy = s.y - local_y;
                let dsz = s.z - local_z;
                if (dsx * dsx + dsy * dsy + dsz * dsz).sqrt() > 1.0 {
                    local_x = s.x;
                    local_y = s.y;
                    local_z = s.z;
                }
            }
            let dx = tx - local_x;
            let dy = ty - local_y;
            let dz = tz - local_z;
            let dist = (dx * dx + dy * dy + dz * dz).sqrt();
            if dist <= 1.5 {
                return Ok(true);
            }
            let mut step_dx = dx;
            let mut step_dy = dy;
            let mut step_dz = dz;
            if dist > MAX_PREDICTION_RADIUS {
                let scale = MAX_PREDICTION_RADIUS / dist;
                step_dx *= scale;
                step_dy *= scale;
                step_dz *= scale;
            }
            local_x += step_dx;
            local_y += step_dy;
            local_z += step_dz;
            let pkt = SbPosition {
                x: local_x,
                y: local_y,
                z: local_z,
                on_ground: true,
            };
            self.connection.send(&pkt).await?;
            tokio::time::sleep(Duration::from_millis(50)).await;
        }
    }

    /// Plan a path to `(tx, ty, tz)` and walk there one tick at a
    /// time, sending Player Position packets at 20 Hz.
    ///
    /// Each move is clamped to ≤5 blocks from the last server-known
    /// position (Paper anti-cheat). Returns `true` on arrival within
    /// 1.5 blocks; `false` on timeout.
    pub async fn walk_to(
        &self,
        tx: f64,
        ty: f64,
        tz: f64,
        timeout_secs: f64,
    ) -> Result<bool, ProtocolError> {
        let start_state = {
            let s = self.state.lock().await;
            if !s.position_known {
                return Err(ProtocolError::DecodeError(
                    "walk_to called before initial position arrived".into(),
                ));
            }
            *s
        };
        let start_pos: Pos = (
            start_state.x.floor() as i32,
            start_state.y.floor() as i32,
            start_state.z.floor() as i32,
        );
        let goal_x = tx.floor() as i32;
        let goal_z = tz.floor() as i32;
        let goal_y_hint = ty.floor() as i32;
        // Resolve a real stand-floor y near the requested goal —
        // spawn-area / cliff terrain frequently has the literal goal
        // cell hanging in air, in which case the literal pathfind
        // never reaches it. Probe a small window: the hint, then
        // +1/-1/+2/-2/+3/-3 (max_fall=3 allows up to -3).
        let goal_pos: Pos = {
            use crate::pathfinding::walkable::stand_floor;
            let candidates = [0, 1, -1, 2, -2, 3, -3];
            let mut chosen = (goal_x, goal_y_hint, goal_z);
            for dy in candidates {
                let cand_y = goal_y_hint + dy;
                if stand_floor(self.world.as_ref(), goal_x, cand_y, goal_z) {
                    chosen = (goal_x, cand_y, goal_z);
                    break;
                }
            }
            chosen
        };

        // Plan the path through the World cache.
        let path_nodes: Vec<Pos> =
            match find_path(self.world.as_ref(), start_pos, goal_pos, 3, 100_000) {
                Ok(p) => p.nodes,
                Err(_) => {
                    return Ok(false);
                }
            };

        // Drive motion through the 20 Hz physics tick — same code
        // path the Python reference uses. Each tick we set
        // PhysicsIntent toward the next waypoint, advance physics
        // against the World cache (handles auto-step on slabs,
        // gravity, water drag, terminal velocity), and send the
        // resulting position. The motion profile now matches the
        // Python reference's, so hazard arena tests and packet-trace
        // parity hold.

        let deadline = tokio::time::Instant::now() + Duration::from_secs_f64(timeout_secs);
        let mut waypoint_idx: usize = 0;
        let mut phys = PhysicsState {
            x: start_state.x,
            y: start_state.y,
            z: start_state.z,
            on_ground: true,
            ..Default::default()
        };
        // Wait one tick at the start so the dispatcher has time to
        // update bot_state from any post-spawn sync_player_position.
        tokio::time::sleep(Duration::from_millis(50)).await;

        loop {
            if tokio::time::Instant::now() > deadline {
                return Ok(false);
            }

            // Re-sync local physics state to dispatcher only on a
            // **teleport-scale** drift (≥ 8 blocks). Paper does NOT
            // send a clientbound `synchronize_player_position` for
            // ordinary walking — it only echoes our outbound
            // serverbound positions. So `bot_state` sits at the last
            // server-confirmed value (initial spawn or last teleport)
            // while the bot walks; the physics state accumulates
            // correct local progress. Resetting `phys` to `bot_state`
            // every tick would freeze the bot in place.
            //
            // 8 blocks exceeds the per-tick walk speed (≤ 0.28 sprint)
            // and the 5-block anti-cheat cap by a wide margin, so any
            // drift this large is a server teleport / knockback / kick
            // recovery and we should snap to it.
            {
                let s = self.state.lock().await;
                let dsx = s.x - phys.x;
                let dsy = s.y - phys.y;
                let dsz = s.z - phys.z;
                if (dsx * dsx + dsy * dsy + dsz * dsz).sqrt() > 8.0 {
                    phys.x = s.x;
                    phys.y = s.y;
                    phys.z = s.z;
                    phys.vx = 0.0;
                    phys.vy = 0.0;
                    phys.vz = 0.0;
                    phys.on_ground = true;
                }
            }

            // Done? Goal-distance check (XZ + small Y tolerance).
            let dx_goal = tx - phys.x;
            let dy_goal = ty - phys.y;
            let dz_goal = tz - phys.z;
            let xz_dist = (dx_goal * dx_goal + dz_goal * dz_goal).sqrt();
            if xz_dist < 0.6 && dy_goal.abs() < 2.0 {
                return Ok(true);
            }

            // Advance waypoint index past anything we've already
            // reached.
            while waypoint_idx + 1 < path_nodes.len() {
                let (wx, _wy, wz) = path_nodes[waypoint_idx];
                let ddx = (wx as f64 + 0.5) - phys.x;
                let ddz = (wz as f64 + 0.5) - phys.z;
                if (ddx * ddx + ddz * ddz).sqrt() < 0.5 {
                    waypoint_idx += 1;
                } else {
                    break;
                }
            }
            if waypoint_idx >= path_nodes.len() {
                tokio::time::sleep(Duration::from_millis(50)).await;
                continue;
            }

            // Build motion intent toward the current waypoint.
            let (wx, wy, wz) = path_nodes[waypoint_idx];
            let target_x = wx as f64 + 0.5;
            let target_z = wz as f64 + 0.5;
            let ddx = target_x - phys.x;
            let ddz = target_z - phys.z;
            let mag = (ddx * ddx + ddz * ddz).sqrt();
            let (intent_dx, intent_dz) = if mag > 1e-6 {
                (ddx / mag, ddz / mag)
            } else {
                (0.0, 0.0)
            };

            // Auto-jump: if the next waypoint sits above the current
            // feet level and we're on the ground (or in water), pulse
            // jump so physics can clear the half-block / full-block step.
            let in_water_now = self.world.is_water(
                phys.x.floor() as i32,
                phys.y.floor() as i32,
                phys.z.floor() as i32,
            );
            let need_jump = (wy as f64) > phys.y.floor() && (phys.on_ground || in_water_now);

            let intent = PhysicsIntent {
                dx: intent_dx,
                dz: intent_dz,
                jump: need_jump,
                sprint: true,
                sneak: false,
            };

            // Run one physics tick against a live World guard so
            // every is_solid query inside the tick stays lock-free.
            phys = {
                let guard = self.world.query_guard();
                let collision = GuardCollision { guard: &guard };
                rphys::tick(&phys, &intent, &collision, in_water_now, false)
            };

            // Sanity: server anti-cheat ≤ 10 blocks/tick. Vanilla
            // physics walks ≈ 0.21 blocks/tick, so we never get
            // close, but reject any pathological state just in case.
            if (phys.x - start_state.x).abs() > 1.0e6 {
                return Err(ProtocolError::DecodeError(
                    "walk_to: physics state diverged catastrophically".into(),
                ));
            }

            let pkt = SbPosition {
                x: phys.x,
                y: phys.y,
                z: phys.z,
                on_ground: phys.on_ground,
            };
            self.connection.send(&pkt).await?;

            tokio::time::sleep(Duration::from_millis(50)).await;
        }
    }
}

/// CollisionWorld adapter over a long-lived World read-guard.
/// Allows physics tick to call is_solid without per-cell locking.
struct GuardCollision<'a> {
    guard: &'a crate::world::cache::WorldQueryGuard<'a>,
}

impl<'a> rphys::CollisionWorld for GuardCollision<'a> {
    #[inline]
    fn is_solid(&self, x: i32, y: i32, z: i32) -> bool {
        self.guard.is_solid(x, y, z)
    }
}

// Silence the unused-import warning if block_table is no longer used
// directly in this file.
#[allow(unused_imports)]
use block_table as _unused_block_table;
