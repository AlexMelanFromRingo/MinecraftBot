//! BitSet codec — VarInt-prefixed array of i64 longs; bit i = longs[i/64] bit i%64.
//!
//! Decodes/encodes via a `BTreeSet<u32>` of set bit indices for sparse,
//! deterministic ordering on encode (needed for byte parity with Python).

use std::collections::BTreeSet;

use crate::codec::{Reader, Writer, varint};
use crate::errors::ProtocolError;

/// Sparse bitset: set of bit indices that are 1.
pub type BitSet = BTreeSet<u32>;

/// Decode a BitSet.
pub fn read<R: Reader + ?Sized>(reader: &mut R) -> Result<BitSet, ProtocolError> {
    let n_longs = varint::read(reader)?;
    if n_longs < 0 {
        return Err(ProtocolError::EncodeError(format!(
            "bitset.length: negative ({n_longs})"
        )));
    }
    let mut out = BTreeSet::new();
    for i in 0..(n_longs as usize) {
        let bytes = reader.read_exact(8)?;
        let mut buf = [0u8; 8];
        buf.copy_from_slice(bytes);
        let chunk = u64::from_be_bytes(buf);
        let base = (i as u32) * 64;
        for j in 0..64 {
            if chunk & (1u64 << j) != 0 {
                out.insert(base + j);
            }
        }
    }
    Ok(out)
}

/// Encode a BitSet.
pub fn write<W: Writer + ?Sized>(value: &BitSet, writer: &mut W) -> Result<(), ProtocolError> {
    if value.is_empty() {
        varint::write(0, writer)?;
        return Ok(());
    }
    let max_bit = *value.iter().next_back().unwrap() as u64;
    let n_longs = (max_bit / 64 + 1) as usize;
    let mut longs = vec![0u64; n_longs];
    for &bit in value {
        longs[(bit as usize) / 64] |= 1u64 << ((bit as u64) % 64);
    }
    varint::write(n_longs as i32, writer)?;
    for chunk in longs {
        writer.write_all(&chunk.to_be_bytes())?;
    }
    Ok(())
}
