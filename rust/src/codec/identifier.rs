//! Identifier codec — namespaced resource location.

use crate::codec::{Reader, Writer, string_codec};
use crate::errors::ProtocolError;

/// Default namespace inserted on decode when the wire string has no colon.
pub const DEFAULT_NAMESPACE: &str = "minecraft";

/// Decode an Identifier; missing namespace gets defaulted to `minecraft`.
pub fn read<R: Reader + ?Sized>(reader: &mut R) -> Result<String, ProtocolError> {
    let raw = string_codec::read(reader)?;
    if raw.contains(':') {
        Ok(raw)
    } else {
        Ok(format!("{}:{}", DEFAULT_NAMESPACE, raw))
    }
}

/// Encode an Identifier as a String.
pub fn write<W: Writer + ?Sized>(value: &str, writer: &mut W) -> Result<(), ProtocolError> {
    if value.is_empty() {
        return Err(ProtocolError::EncodeError("identifier: empty".into()));
    }
    string_codec::write(value, writer)
}
