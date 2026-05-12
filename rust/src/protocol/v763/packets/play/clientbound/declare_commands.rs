//! Packet `declare_commands`. Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec as string, varint,
    varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x10;

/// Opaque carrier: the wire format is a deeply nested command tree
/// we don't fully parse in the bot layer (the client never needs to
/// reconstruct it). Round-trip uses the raw payload bytes.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct DeclareCommands {
    pub payload: Vec<u8>,
}

impl DeclareCommands {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        Ok(Self {
            payload: reader.read_exact(reader.remaining())?.to_vec(),
        })
    }
}
impl ClientboundPacket for DeclareCommands {
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
