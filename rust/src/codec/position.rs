//! Position codec — packed 26-12-26 signed bigendian u64 (x:26, z:26, y:12).

use crate::codec::{Reader, Writer};
use crate::errors::ProtocolError;

/// World position as (x, y, z), each signed integer.
pub type Position = (i32, i32, i32);

/// Sign-extend `value` from `bits` bits to a full i64.
fn sign_extend(value: u64, bits: u32) -> i64 {
    let mask = (1u64 << bits) - 1;
    let v = value & mask;
    if v & (1u64 << (bits - 1)) != 0 {
        (v as i64) - (1i64 << bits)
    } else {
        v as i64
    }
}

/// Decode a Position from 8 big-endian bytes.
pub fn read<R: Reader + ?Sized>(reader: &mut R) -> Result<Position, ProtocolError> {
    let bytes = reader.read_exact(8)?;
    let mut buf = [0u8; 8];
    buf.copy_from_slice(bytes);
    let val = u64::from_be_bytes(buf);
    let x = sign_extend((val >> 38) & 0x3FF_FFFF, 26) as i32;
    let z = sign_extend((val >> 12) & 0x3FF_FFFF, 26) as i32;
    let y = sign_extend(val & 0xFFF, 12) as i32;
    Ok((x, y, z))
}

/// Encode `(x, y, z)` into 8 big-endian bytes.
pub fn write<W: Writer + ?Sized>(value: &Position, writer: &mut W) -> Result<(), ProtocolError> {
    let (x, y, z) = *value;
    let xu = (x as u64) & 0x3FF_FFFF;
    let zu = (z as u64) & 0x3FF_FFFF;
    let yu = (y as u64) & 0xFFF;
    let val = (xu << 38) | (zu << 12) | yu;
    writer.write_all(&val.to_be_bytes())
}
