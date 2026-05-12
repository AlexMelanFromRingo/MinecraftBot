//! Connection states and packet directions for protocol 763.

/// Discrete protocol phases of a Connection.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum ConnectionState {
    /// Pre-handshake state; client announces protocol + next state.
    Handshaking = 0,
    /// Server-list ping flow.
    Status = 1,
    /// Login handshake.
    Login = 2,
    /// Active gameplay.
    Play = 3,
}

impl ConnectionState {
    /// Lowercase string used in WireLog JSONL `state` field.
    pub fn label(self) -> &'static str {
        match self {
            Self::Handshaking => "handshaking",
            Self::Status => "status",
            Self::Login => "login",
            Self::Play => "play",
        }
    }
}

/// Packet flow direction.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum Direction {
    /// Server → client.
    Clientbound = 0,
    /// Client → server.
    Serverbound = 1,
}

impl Direction {
    /// Two-letter label used in WireLog JSONL `dir` field.
    pub fn label(self) -> &'static str {
        match self {
            Self::Clientbound => "rx",
            Self::Serverbound => "tx",
        }
    }
}
