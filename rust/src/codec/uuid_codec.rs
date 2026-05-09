//! UUID codec — 16 bytes, two big-endian i64 halves.
//!
//! Represents a UUID as `[u8; 16]` (raw bytes). Helpers are provided to
//! convert to/from the canonical `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
//! string form so byte parity with Python's `uuid.UUID` round-trips.

use crate::codec::{Reader, Writer};
use crate::errors::ProtocolError;

/// 128-bit UUID stored most-significant-byte first.
pub type Uuid = [u8; 16];

/// Decode 16 bytes from `reader`.
pub fn read<R: Reader + ?Sized>(reader: &mut R) -> Result<Uuid, ProtocolError> {
    let bytes = reader.read_exact(16)?;
    let mut out = [0u8; 16];
    out.copy_from_slice(bytes);
    Ok(out)
}

/// Encode 16 bytes to `writer`.
pub fn write<W: Writer + ?Sized>(value: &Uuid, writer: &mut W) -> Result<(), ProtocolError> {
    writer.write_all(value)
}

/// Parse a canonical `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` (or no-dash hex) string.
pub fn parse_str(s: &str) -> Result<Uuid, ProtocolError> {
    let hex: String = s.chars().filter(|c| *c != '-').collect();
    if hex.len() != 32 {
        return Err(ProtocolError::EncodeError(format!(
            "uuid string length {} (expected 32 hex chars)",
            hex.len()
        )));
    }
    let mut out = [0u8; 16];
    for (i, byte) in out.iter_mut().enumerate() {
        let s = &hex[2 * i..2 * i + 2];
        *byte = u8::from_str_radix(s, 16).map_err(|e| {
            ProtocolError::EncodeError(format!("uuid parse: {e}"))
        })?;
    }
    Ok(out)
}

/// Format as canonical 8-4-4-4-12 hex string.
pub fn to_string(u: &Uuid) -> String {
    let h: String = u.iter().map(|b| format!("{:02x}", b)).collect();
    format!(
        "{}-{}-{}-{}-{}",
        &h[0..8],
        &h[8..12],
        &h[12..16],
        &h[16..20],
        &h[20..32]
    )
}
