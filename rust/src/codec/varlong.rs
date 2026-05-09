//! VarLong codec (i64, 1..10 bytes).

use crate::codec::{Reader, Writer};
use crate::errors::ProtocolError;

/// Maximum number of bytes a VarLong can occupy.
pub const MAX_BYTES: usize = 10;

/// Decode a VarLong as a signed 64-bit integer.
pub fn read<R: Reader + ?Sized>(reader: &mut R) -> Result<i64, ProtocolError> {
    let mut result: u128 = 0;
    for i in 0..MAX_BYTES {
        let b = reader.read_exact(1)?[0];
        result |= ((b & 0x7F) as u128) << (7 * i);
        if (b & 0x80) == 0 {
            let truncated = result as u64;
            return Ok(truncated as i64);
        }
    }
    Err(ProtocolError::oversized_varint(MAX_BYTES + 1))
}

/// Encode an i64 as a VarLong.
pub fn write<W: Writer + ?Sized>(value: i64, writer: &mut W) -> Result<(), ProtocolError> {
    let mut u = value as u64;
    let mut buf = [0u8; MAX_BYTES];
    let mut i = 0;
    loop {
        if (u & !0x7F) == 0 {
            buf[i] = u as u8;
            i += 1;
            break;
        }
        buf[i] = ((u & 0x7F) | 0x80) as u8;
        i += 1;
        u >>= 7;
    }
    writer.write_all(&buf[..i])
}
