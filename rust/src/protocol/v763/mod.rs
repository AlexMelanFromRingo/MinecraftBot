//! Protocol 763 — Minecraft Java Edition 1.20.1.

pub mod packets;
pub mod registry;
pub mod states;

pub use registry::{
    encode_clientbound, encode_serverbound, AnyPacket, ClientboundPacket, CodecRegistry, DecodeFn,
    ServerboundPacket,
};
