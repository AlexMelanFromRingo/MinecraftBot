//! VarInt-prefixed UTF-8 string codec.

use crate::codec::{varint, Reader, Writer};
use crate::errors::ProtocolError;

/// Default maximum length (in bytes/chars) for the protocol-wide cap.
pub const MAX_LENGTH: usize = 32_767;

/// Decode a VarInt-prefixed UTF-8 string.
pub fn read<R: Reader + ?Sized>(reader: &mut R) -> Result<String, ProtocolError> {
    read_with_max(reader, MAX_LENGTH)
}

/// Decode a VarInt-prefixed UTF-8 string with a custom max length.
pub fn read_with_max<R: Reader + ?Sized>(
    reader: &mut R,
    max_length: usize,
) -> Result<String, ProtocolError> {
    let n_bytes = varint::read(reader)?;
    if n_bytes < 0 {
        return Err(ProtocolError::EncodeError(format!(
            "string.length: negative ({n_bytes})"
        )));
    }
    let bytes = reader.read_exact(n_bytes as usize)?.to_vec();
    let s = String::from_utf8(bytes)
        .map_err(|e| ProtocolError::DecodeError(format!("non-utf-8 string: {e}")))?;
    if s.chars().count() > max_length {
        return Err(ProtocolError::EncodeError(format!(
            "string.length: {} exceeds max {}",
            s.chars().count(),
            max_length
        )));
    }
    Ok(s)
}

/// Encode a string as VarInt-prefixed UTF-8.
pub fn write<W: Writer + ?Sized>(value: &str, writer: &mut W) -> Result<(), ProtocolError> {
    write_with_max(value, writer, MAX_LENGTH)
}

/// Encode with a custom max length.
pub fn write_with_max<W: Writer + ?Sized>(
    value: &str,
    writer: &mut W,
    max_length: usize,
) -> Result<(), ProtocolError> {
    if value.chars().count() > max_length {
        return Err(ProtocolError::EncodeError(format!(
            "string.length: {} exceeds max {}",
            value.chars().count(),
            max_length
        )));
    }
    let raw = value.as_bytes();
    varint::write(raw.len() as i32, writer)?;
    writer.write_all(raw)
}
