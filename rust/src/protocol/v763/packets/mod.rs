//! Per-protocol packet implementations for protocol 763 (T120-T122).
//!
//! Layout mirrors `python/minecraft_bot/protocol/v763/packets/`:
//! one Rust module per `(state, direction)`, one source file per packet.

pub mod handshaking;
pub mod login;
pub mod play;
pub mod status;
