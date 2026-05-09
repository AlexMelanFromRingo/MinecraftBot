//! VarInt codec (i32, 1..5 bytes).

use crate::codec::{Reader, Writer};
use crate::errors::ProtocolError;

/// Maximum number of bytes a VarInt can occupy.
pub const MAX_BYTES: usize = 5;

/// Decode a VarInt as a signed 32-bit integer.
pub fn read<R: Reader + ?Sized>(reader: &mut R) -> Result<i32, ProtocolError> {
    let mut result: u64 = 0;
    for i in 0..MAX_BYTES {
        let b = reader.read_exact(1)?[0];
        result |= ((b & 0x7F) as u64) << (7 * i);
        if (b & 0x80) == 0 {
            // Sign-extend from bit 31 (two's complement i32).
            let truncated = result as u32;
            return Ok(truncated as i32);
        }
    }
    Err(ProtocolError::oversized_varint(MAX_BYTES + 1))
}

/// Encode an i32 as a VarInt.
pub fn write<W: Writer + ?Sized>(value: i32, writer: &mut W) -> Result<(), ProtocolError> {
    let mut u = (value as u32) as u64;
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

/// Number of bytes [`write`] would emit for `value`.
pub fn encoded_size(value: i32) -> usize {
    let u = value as u32;
    if u < 0x80 {
        1
    } else if u < 0x4000 {
        2
    } else if u < 0x20_0000 {
        3
    } else if u < 0x1000_0000 {
        4
    } else {
        5
    }
}
