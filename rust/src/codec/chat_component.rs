//! ChatComponent codec — VarInt-prefixed JSON string.

use crate::codec::{string_codec, Reader, Writer};
use crate::errors::ProtocolError;

/// Maximum chat-component byte length.
pub const MAX_LENGTH: usize = 262_144;

/// Decode a chat component (raw JSON).
pub fn read<R: Reader + ?Sized>(reader: &mut R) -> Result<String, ProtocolError> {
    string_codec::read_with_max(reader, MAX_LENGTH)
}

/// Encode a chat component.
pub fn write<W: Writer + ?Sized>(value: &str, writer: &mut W) -> Result<(), ProtocolError> {
    string_codec::write_with_max(value, writer, MAX_LENGTH)
}
