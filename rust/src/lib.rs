//! `minecraft_bot` — Minecraft Java Edition bot framework (Rust parity mirror).
//!
//! The Python crate at `python/minecraft_bot/` is the canonical reference;
//! this crate mirrors it byte-for-byte. See
//! `specs/001-protocol-foundation/contracts/rust-api.md` for the normative
//! public API contract.

#![warn(missing_docs)]

pub mod codec;
pub mod errors;
pub mod protocol;

pub use crate::errors::ProtocolError;
pub use crate::protocol::{ProtocolVersion, V_1_20_1, V_1_20_2};
pub use crate::protocol::v763::states::{ConnectionState, Direction};
