//! Packet `select_advancement_tab`. Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec as string, varint,
    varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x44;

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct SelectAdvancementTab {
    pub id: Option<String>,
}
impl SelectAdvancementTab {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let p = reader.read_exact(1)?[0];
        let id = match p {
            0 => None,
            1 => Some(string::read(reader)?),
            other => return Err(ProtocolError::DecodeError(format!("present: {}", other))),
        };
        Ok(Self { id })
    }
}
impl ClientboundPacket for SelectAdvancementTab {
    fn state(&self) -> ConnectionState {
        ConnectionState::Play
    }
    fn packet_id(&self) -> i32 {
        PACKET_ID
    }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        match &self.id {
            None => writer.write_all(&[0]),
            Some(s) => {
                writer.write_all(&[1])?;
                string::write(s, writer)
            }
        }
    }
}
