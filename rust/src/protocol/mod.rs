//! Protocol-version-aware module root.

pub mod v763;

/// Numeric identifier for a wire protocol version.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ProtocolVersion {
    /// Wire protocol number, e.g. 763.
    pub number: i32,
    /// Informational display name, e.g. "1.20.1".
    pub display_name: &'static str,
}

/// Minecraft 1.20.1 (protocol 763).
pub const V_1_20_1: ProtocolVersion = ProtocolVersion {
    number: 763,
    display_name: "1.20.1",
};

/// Minecraft 1.20.2 (protocol 764) — demonstrative only in this milestone.
pub const V_1_20_2: ProtocolVersion = ProtocolVersion {
    number: 764,
    display_name: "1.20.2",
};
