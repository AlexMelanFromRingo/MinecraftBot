//! Structured decoder for the `map_chunk` packet payload — Rust port
//! of `python/minecraft_bot/world/decode_chunk.py`.

use crate::codec::{BytesReader, Reader as RustReader, nbt, varint};
use crate::errors::ProtocolError;
use crate::world::chunk::{BlockEntityRecord, Chunk, ChunkSection, PalettedContainer};

// Per-section block-state paletted-container bit-widths.
const BLOCK_MIN_INDEXED_BITS: u8 = 4;
const BLOCK_MAX_INDEXED_BITS: u8 = 8;
const BLOCK_DIRECT_BITS: u8 = 15;
// Per-section biome paletted-container bit-widths.
const BIOME_MIN_INDEXED_BITS: u8 = 1;
const BIOME_MAX_INDEXED_BITS: u8 = 3;
const BIOME_DIRECT_BITS: u8 = 6;

fn read_i16_be<R: RustReader + ?Sized>(reader: &mut R) -> Result<i16, ProtocolError> {
    let bytes = reader.read_exact(2)?;
    Ok(i16::from_be_bytes([bytes[0], bytes[1]]))
}

fn read_i64_be<R: RustReader + ?Sized>(reader: &mut R) -> Result<i64, ProtocolError> {
    let bytes = reader.read_exact(8)?;
    let mut buf = [0u8; 8];
    buf.copy_from_slice(bytes);
    Ok(i64::from_be_bytes(buf))
}

fn read_paletted<R: RustReader + ?Sized>(
    reader: &mut R,
    is_block: bool,
) -> Result<PalettedContainer, ProtocolError> {
    let bits = reader.read_exact(1)?[0];
    if bits == 0 {
        // Single-value mode: one varint palette entry, then a long
        // count (typically 0 in the spec; tolerate non-zero).
        let value = varint::read(reader)?;
        let n_longs = varint::read(reader)?;
        if n_longs > 0 {
            reader.read_exact(8 * n_longs as usize)?;
        }
        return Ok(PalettedContainer::single(value));
    }

    let (max_indexed, min_bits, direct_bits) = if is_block {
        (BLOCK_MAX_INDEXED_BITS, BLOCK_MIN_INDEXED_BITS, BLOCK_DIRECT_BITS)
    } else {
        (BIOME_MAX_INDEXED_BITS, BIOME_MIN_INDEXED_BITS, BIOME_DIRECT_BITS)
    };

    if bits <= max_indexed {
        let eff_bits = bits.max(min_bits);
        let palette_size = varint::read(reader)?;
        let mut palette = Vec::with_capacity(palette_size.max(0) as usize);
        for _ in 0..palette_size {
            palette.push(varint::read(reader)?);
        }
        let n_longs = varint::read(reader)?;
        let mut data = Vec::with_capacity(n_longs.max(0) as usize);
        for _ in 0..n_longs {
            data.push(read_i64_be(reader)?);
        }
        return Ok(PalettedContainer::indexed(eff_bits, palette, data));
    }

    // Direct mode.
    let n_longs = varint::read(reader)?;
    let mut data = Vec::with_capacity(n_longs.max(0) as usize);
    for _ in 0..n_longs {
        data.push(read_i64_be(reader)?);
    }
    Ok(PalettedContainer::direct(direct_bits, data))
}

/// Decode the trailing payload of a `map_chunk` packet into a
/// [`Chunk`]. The caller has already peeled off the `(chunk_x,
/// chunk_z)` i32×2 header.
pub fn decode(
    payload: &[u8],
    cx: i32,
    cz: i32,
    min_y: i32,
    section_count: i32,
) -> Result<Chunk, ProtocolError> {
    let mut reader = BytesReader::new(payload);

    // 1) Heightmaps NBT (network NBT — has root name in 1.20.1).
    let heightmaps_tag = nbt::read(&mut reader)?;
    // We don't keep the parsed NBT here (the existing Chunk struct
    // stores opaque bytes); a future light-aware feature can decode
    // them. For parity, hold them as an empty Vec for now and write
    // tag back if needed.
    let _ = heightmaps_tag;

    // 2) Section data inside a length-prefixed buffer.
    let data_len = varint::read(&mut reader)?;
    if data_len < 0 {
        return Err(ProtocolError::DecodeError(format!(
            "negative section-data length: {}",
            data_len
        )));
    }
    let sec_slice = reader.read_exact(data_len as usize)?.to_vec();
    let mut sec_reader = BytesReader::new(&sec_slice);
    let mut sections: Vec<ChunkSection> = Vec::with_capacity(section_count.max(0) as usize);
    for _ in 0..section_count {
        let block_count = read_i16_be(&mut sec_reader)? as i32;
        let block_states = read_paletted(&mut sec_reader, true)?;
        let biomes = read_paletted(&mut sec_reader, false)?;
        sections.push(ChunkSection {
            block_count,
            block_states,
            biomes,
        });
    }

    // 3) Block entities array.
    let n_be = varint::read(&mut reader)?;
    let mut block_entities = std::collections::HashMap::with_capacity(n_be.max(0) as usize);
    let base_x = cx * 16;
    let base_z = cz * 16;
    for _ in 0..n_be {
        let packed = reader.read_exact(1)?[0];
        let lx = ((packed >> 4) & 0xF) as i32;
        let lz = (packed & 0xF) as i32;
        let y = read_i16_be(&mut reader)? as i32;
        let type_id = varint::read(&mut reader)?;
        let _nbt = nbt::read(&mut reader)?;
        let wx = base_x + lx;
        let wz = base_z + lz;
        block_entities.insert(
            (wx, y, wz),
            BlockEntityRecord {
                x: wx,
                y,
                z: wz,
                type_id,
                nbt: Vec::new(),
            },
        );
    }

    // Light data trailing bytes intentionally not decoded (matches
    // Python reference Phase 2c scope).

    Ok(Chunk {
        cx,
        cz,
        sections,
        block_entities,
        heightmaps: Vec::new(),
        min_y,
        section_count,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::codec::BytesWriter;
    use crate::codec::Writer as RustWriter;

    /// Build a minimal map_chunk payload for a chunk with all-air
    /// sections, no heightmaps, no block-entities.
    fn build_empty_payload(section_count: i32) -> Vec<u8> {
        let mut buf = BytesWriter::new();
        // 1. heightmaps NBT: just an end tag (NBT TAG_End = 0)
        buf.write_all(&[0u8]).unwrap();
        // 2. section data buffer: each section is
        //      block_count (i16) + block_states + biomes
        //    where block_states/biomes are single-value mode:
        //      bits(1) = 0, value (varint) = 0, n_longs(varint) = 0
        let mut sec = BytesWriter::new();
        for _ in 0..section_count {
            // block_count = 0
            sec.write_all(&0i16.to_be_bytes()).unwrap();
            // single-value block states (air)
            sec.write_all(&[0u8]).unwrap();
            varint::write(0, &mut sec).unwrap();
            varint::write(0, &mut sec).unwrap();
            // single-value biomes
            sec.write_all(&[0u8]).unwrap();
            varint::write(0, &mut sec).unwrap();
            varint::write(0, &mut sec).unwrap();
        }
        let sec_bytes = sec.into_bytes();
        varint::write(sec_bytes.len() as i32, &mut buf).unwrap();
        buf.write_all(&sec_bytes).unwrap();
        // 3. block entities count = 0
        varint::write(0, &mut buf).unwrap();
        buf.into_bytes()
    }

    #[test]
    fn empty_chunk_decodes_with_air_sections() {
        let payload = build_empty_payload(24);
        let chunk = decode(&payload, 0, 0, -64, 24).unwrap();
        assert_eq!(chunk.cx, 0);
        assert_eq!(chunk.cz, 0);
        assert_eq!(chunk.sections.len(), 24);
        for s in &chunk.sections {
            assert_eq!(s.block_count, 0);
            // Single-value mode air everywhere.
            for i in 0..4096 {
                assert_eq!(s.block_states.get(i), 0);
            }
        }
        assert!(chunk.block_entities.is_empty());
    }
}
