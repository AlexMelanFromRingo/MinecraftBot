//! Packet `stop_sound` (play/clientbound). Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec as string, varint,
    varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x63;

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct StopSound {
    pub flags: i8,
    pub source: Option<i32>,
    pub sound: Option<String>,
}

impl StopSound {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let flags = reader.read_exact(1)?[0] as i8;
        let source = if flags & 0x01 != 0 {
            Some(varint::read(reader)?)
        } else {
            None
        };
        let sound = if flags & 0x02 != 0 {
            Some(string::read(reader)?)
        } else {
            None
        };
        Ok(Self {
            flags,
            source,
            sound,
        })
    }
}

impl ClientboundPacket for StopSound {
    fn state(&self) -> ConnectionState {
        ConnectionState::Play
    }
    fn packet_id(&self) -> i32 {
        PACKET_ID
    }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        writer.write_all(&[self.flags as u8])?;
        if let Some(s) = self.source {
            varint::write(s, writer)?;
        }
        if let Some(s) = &self.sound {
            string::write(s, writer)?;
        }
        Ok(())
    }
}
