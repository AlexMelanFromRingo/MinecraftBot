//! Typed error hierarchy mirroring `python/minecraft_bot/errors.py`.

use thiserror::Error;

/// Variant set parallel to the Python `ProtocolError` class hierarchy.
#[derive(Debug, Error)]
#[non_exhaustive]
pub enum ProtocolError {
    /// Server rejected the handshake or peer aborted before login.
    #[error("handshake failed: {0}")]
    HandshakeFailed(String),

    /// Server rejected the login.
    #[error("login failed: {0}")]
    LoginFailed(String),

    /// Server-initiated disconnect during play.
    #[error("disconnected: {0}")]
    Disconnected(String),

    /// The server sent a clientbound disconnect packet.
    #[error("kicked by server: {0}")]
    KickedByServer(String),

    /// TCP-level loss outside a clean disconnect.
    #[error("connection dropped: {0}")]
    ConnectionDropped(String),

    /// Keep-alive timeout.
    #[error("keep-alive timeout")]
    KeepAliveTimeout,

    /// OS-reported peer reset.
    #[error("peer reset")]
    PeerReset,

    /// Generic decode error with a message.
    #[error("decode error: {0}")]
    DecodeError(String),

    /// A packet ID that has no schema registered.
    #[error("unknown packet id: state={state} dir={direction} id={id}")]
    UnknownPacketId {
        /// Connection state at decode time.
        state: String,
        /// Packet direction.
        direction: String,
        /// Numeric packet id within the (state, direction).
        id: i32,
    },

    /// VarInt/VarLong consumed more bytes than allowed.
    #[error("oversized varint ({byte_count} bytes)")]
    OversizedVarInt {
        /// How many bytes were consumed before failure.
        byte_count: usize,
    },

    /// A codec asked for more bytes than remained.
    #[error("incomplete read: requested {requested}, available {available}")]
    IncompleteRead {
        /// Number of bytes requested.
        requested: usize,
        /// Number of bytes available.
        available: usize,
    },

    /// An NBT tag was structurally invalid.
    #[error("malformed NBT: {0}")]
    MalformedNbt(String),

    /// A value was out of its protocol-defined range.
    #[error("encode error: {0}")]
    EncodeError(String),

    /// Connection was closed before/after the operation.
    #[error("connection closed")]
    ConnectionClosed,

    /// I/O error from the OS (network or filesystem).
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
}

impl ProtocolError {
    /// Convenience constructor for `IncompleteRead`.
    pub fn incomplete(requested: usize, available: usize) -> Self {
        Self::IncompleteRead { requested, available }
    }

    /// Convenience constructor for `OversizedVarInt`.
    pub fn oversized_varint(byte_count: usize) -> Self {
        Self::OversizedVarInt { byte_count }
    }
}
