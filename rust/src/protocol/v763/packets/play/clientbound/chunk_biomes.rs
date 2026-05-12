//! Packet `chunk_biomes` (play/clientbound). Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec as string, varint,
    varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x0D;

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct ChunkBiomeEntry {
    pub chunk_x: i32,
    pub chunk_z: i32,
    pub data: Vec<u8>,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct ChunkBiomes {
    pub entries: Vec<ChunkBiomeEntry>,
}

impl ChunkBiomes {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let n = varint::read(reader)? as usize;
        let mut entries = Vec::with_capacity(n);
        for _ in 0..n {
            let b = reader.read_exact(8)?;
            let chunk_x = i32::from_be_bytes([b[0], b[1], b[2], b[3]]);
            let chunk_z = i32::from_be_bytes([b[4], b[5], b[6], b[7]]);
            let data_len = varint::read(reader)? as usize;
            let data = reader.read_exact(data_len)?.to_vec();
            entries.push(ChunkBiomeEntry {
                chunk_x,
                chunk_z,
                data,
            });
        }
        Ok(Self { entries })
    }
}

impl ClientboundPacket for ChunkBiomes {
    fn state(&self) -> ConnectionState {
        ConnectionState::Play
    }
    fn packet_id(&self) -> i32 {
        PACKET_ID
    }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        varint::write(self.entries.len() as i32, writer)?;
        for e in &self.entries {
            writer.write_all(&e.chunk_x.to_be_bytes())?;
            writer.write_all(&e.chunk_z.to_be_bytes())?;
            varint::write(e.data.len() as i32, writer)?;
            writer.write_all(&e.data)?;
        }
        Ok(())
    }
}
