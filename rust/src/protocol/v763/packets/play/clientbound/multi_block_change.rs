//! Packet `multi_block_change` (play/clientbound). Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec as string, varint,
    varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x43;

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct MultiBlockChange {
    pub chunk_section_x: i32,
    pub chunk_section_z: i32,
    pub chunk_section_y: i32,
    pub records: Vec<i64>,
}

fn sign_extend(v: i64, bits: i32) -> i32 {
    let mask: i64 = (1i64 << bits) - 1;
    let mut v = v & mask;
    if v & (1i64 << (bits - 1)) != 0 {
        v -= 1i64 << bits;
    }
    v as i32
}

impl MultiBlockChange {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let b = reader.read_exact(8)?;
        let packed = i64::from_be_bytes([b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7]]);
        let cy = sign_extend(packed & 0xFFFFF, 20);
        let cz = sign_extend((packed >> 20) & 0x3FFFFF, 22);
        let cx = sign_extend((packed >> 42) & 0x3FFFFF, 22);
        let n = varint::read(reader)? as usize;
        let mut records = Vec::with_capacity(n);
        for _ in 0..n {
            records.push(varlong::read(reader)?);
        }
        Ok(Self {
            chunk_section_x: cx,
            chunk_section_z: cz,
            chunk_section_y: cy,
            records,
        })
    }
}

impl ClientboundPacket for MultiBlockChange {
    fn state(&self) -> ConnectionState {
        ConnectionState::Play
    }
    fn packet_id(&self) -> i32 {
        PACKET_ID
    }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        let packed: i64 = ((self.chunk_section_x as i64 & 0x3FFFFF) << 42)
            | ((self.chunk_section_z as i64 & 0x3FFFFF) << 20)
            | (self.chunk_section_y as i64 & 0xFFFFF);
        writer.write_all(&packed.to_be_bytes())?;
        varint::write(self.records.len() as i32, writer)?;
        for r in &self.records {
            varlong::write(*r, writer)?;
        }
        Ok(())
    }
}
