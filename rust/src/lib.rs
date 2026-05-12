//! `minecraft_bot` — Minecraft Java Edition bot framework (Rust parity mirror).
//!
//! The Python crate at `python/minecraft_bot/` is the canonical reference;
//! this crate mirrors it byte-for-byte. See
//! `specs/001-protocol-foundation/contracts/rust-api.md` for the normative
//! public API contract.

#![warn(missing_docs)]

pub mod codec;
pub mod connection;
pub mod errors;
pub mod framer;
pub mod protocol;
pub mod wire_log;
// 003 — bot-API port.
pub mod bot;
pub mod effects;
pub mod pathfinding;
pub mod physics;
pub mod world;

pub use crate::connection::{offline_uuid, Connection, Reconnected, ReconnectPolicy};
pub use crate::errors::ProtocolError;
pub use crate::framer::{Framer, MAX_PACKET_SIZE};
pub use crate::protocol::{ProtocolVersion, V_1_20_1, V_1_20_2};
pub use crate::protocol::v763::states::{ConnectionState, Direction};
pub use crate::world::{Chunk, ChunkSection, PalettedContainer, World};
