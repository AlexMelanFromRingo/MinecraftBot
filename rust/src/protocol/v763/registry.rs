//! Per-protocol-version packet registry (T119).
//!
//! Mirror of `python/minecraft_bot/protocol/v763/registry.py`. Each
//! concrete packet implements one of the [`ClientboundPacket`] or
//! [`ServerboundPacket`] traits. The [`CodecRegistry`] maps a
//! `(state, direction, id)` triple to a decoder closure.

use std::collections::HashMap;
use std::sync::Arc;

use crate::codec::{BytesReader, BytesWriter, Reader, Writer};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::{ConnectionState, Direction};

/// A clientbound (server → client) packet.
pub trait ClientboundPacket: Send + Sync + std::fmt::Debug {
    /// Connection state this packet belongs to.
    fn state(&self) -> ConnectionState;
    /// Numeric packet id within `(state, clientbound)`.
    fn packet_id(&self) -> i32;
    /// Encode the packet payload (the bytes AFTER the leading id varint)
    /// into `writer`.
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError>;
}

/// A serverbound (client → server) packet.
pub trait ServerboundPacket: Send + Sync + std::fmt::Debug {
    /// Connection state this packet belongs to.
    fn state(&self) -> ConnectionState;
    /// Numeric packet id within `(state, serverbound)`.
    fn packet_id(&self) -> i32;
    /// Encode the packet payload into `writer`.
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError>;
}

/// Boxed decoded packet — either client- or server-bound depending on
/// the registry's lookup direction.
pub type AnyPacket = Box<dyn std::any::Any + Send + Sync>;

/// Boxed decode function pointer for a single `(state, dir, id)` slot.
pub type DecodeFn =
    Arc<dyn (Fn(&mut BytesReader<'_>) -> Result<AnyPacket, ProtocolError>) + Send + Sync>;

/// `(state, direction, packet_id) → decode function` registry.
#[derive(Clone, Default)]
pub struct CodecRegistry {
    decoders: HashMap<(ConnectionState, Direction, i32), DecodeFn>,
}

impl CodecRegistry {
    /// Construct an empty registry.
    pub fn new() -> Self {
        Self {
            decoders: HashMap::new(),
        }
    }

    /// Register a decode function for `(state, dir, id)`. Calling this
    /// twice for the same key replaces the prior entry.
    pub fn register(&mut self, state: ConnectionState, dir: Direction, id: i32, decode: DecodeFn) {
        self.decoders.insert((state, dir, id), decode);
    }

    /// Look up and invoke a decoder, returning the decoded packet
    /// (or [`ProtocolError::UnknownPacketId`] if no entry).
    pub fn decode(
        &self,
        state: ConnectionState,
        dir: Direction,
        id: i32,
        reader: &mut BytesReader<'_>,
    ) -> Result<AnyPacket, ProtocolError> {
        let key = (state, dir, id);
        let decode = self
            .decoders
            .get(&key)
            .ok_or_else(|| ProtocolError::UnknownPacketId {
                state: state.label().to_string(),
                direction: dir.label().to_string(),
                id,
            })?;
        decode(reader)
    }

    /// Number of registered decoders.
    pub fn len(&self) -> usize {
        self.decoders.len()
    }

    /// True iff the registry has no decoders registered.
    pub fn is_empty(&self) -> bool {
        self.decoders.is_empty()
    }
}

/// Helper for packet modules: encode `(packet_id_varint + payload)` for
/// a serverbound packet, returning the body bytes the framer will wrap.
pub fn encode_serverbound<P: ServerboundPacket>(packet: &P) -> Result<Vec<u8>, ProtocolError> {
    let mut w = BytesWriter::new();
    crate::codec::varint::write(packet.packet_id(), &mut w)?;
    packet.encode(&mut w)?;
    Ok(w.into_bytes())
}

/// Helper: encode `(packet_id_varint + payload)` for a clientbound
/// packet — used by WireLog replay and tests, not the wire path.
pub fn encode_clientbound<P: ClientboundPacket>(packet: &P) -> Result<Vec<u8>, ProtocolError> {
    let mut w = BytesWriter::new();
    crate::codec::varint::write(packet.packet_id(), &mut w)?;
    packet.encode(&mut w)?;
    Ok(w.into_bytes())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Debug)]
    struct DummyClientbound;
    impl ClientboundPacket for DummyClientbound {
        fn state(&self) -> ConnectionState {
            ConnectionState::Status
        }
        fn packet_id(&self) -> i32 {
            0x42
        }
        fn encode(&self, _w: &mut BytesWriter) -> Result<(), ProtocolError> {
            Ok(())
        }
    }

    #[test]
    fn unknown_id_returns_error() {
        let r = CodecRegistry::new();
        let mut br = BytesReader::new(&[]);
        let result = r.decode(
            ConnectionState::Status,
            Direction::Clientbound,
            0x99,
            &mut br,
        );
        assert!(matches!(result, Err(ProtocolError::UnknownPacketId { .. })));
    }

    #[test]
    fn register_then_decode_round_trip() {
        let mut r = CodecRegistry::new();
        r.register(
            ConnectionState::Status,
            Direction::Clientbound,
            0x42,
            Arc::new(|_reader| Ok(Box::new(DummyClientbound) as AnyPacket)),
        );
        let mut br = BytesReader::new(&[]);
        let result = r.decode(
            ConnectionState::Status,
            Direction::Clientbound,
            0x42,
            &mut br,
        );
        assert!(result.is_ok());
    }

    #[test]
    fn encode_serverbound_round_trip() {
        struct Echo {
            id: i32,
        }
        impl std::fmt::Debug for Echo {
            fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
                write!(f, "Echo({})", self.id)
            }
        }
        impl ServerboundPacket for Echo {
            fn state(&self) -> ConnectionState {
                ConnectionState::Handshaking
            }
            fn packet_id(&self) -> i32 {
                self.id
            }
            fn encode(&self, _w: &mut BytesWriter) -> Result<(), ProtocolError> {
                Ok(())
            }
        }
        let bytes = encode_serverbound(&Echo { id: 0 }).unwrap();
        assert_eq!(bytes, vec![0u8]);
    }
}
