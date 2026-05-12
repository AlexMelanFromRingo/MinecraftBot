//! Packet `update_structure_block`. Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec as string, varint,
    varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ServerboundPacket;

pub const PACKET_ID: i32 = 0x2D;

/// Complex creative-only packet; framework keeps the payload opaque
/// since the bot is unlikely to send it.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct UpdateStructureBlock {
    pub payload: Vec<u8>,
}

impl UpdateStructureBlock {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        Ok(Self {
            payload: reader.read_exact(reader.remaining())?.to_vec(),
        })
    }
}
impl ServerboundPacket for UpdateStructureBlock {
    fn state(&self) -> ConnectionState {
        ConnectionState::Play
    }
    fn packet_id(&self) -> i32 {
        PACKET_ID
    }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        writer.write_all(&self.payload)
    }
}
