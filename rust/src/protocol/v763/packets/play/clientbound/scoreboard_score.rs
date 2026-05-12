//! Packet `scoreboard_score` (play/clientbound). Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec as string, varint,
    varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x5B;

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct ScoreboardScore {
    pub item_name: String,
    pub action: i32,
    pub score_name: String,
    pub value: Option<i32>,
}

impl ScoreboardScore {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let item_name = string::read(reader)?;
        let action = varint::read(reader)?;
        let score_name = string::read(reader)?;
        let value = if action == 1 {
            None
        } else {
            Some(varint::read(reader)?)
        };
        Ok(Self {
            item_name,
            action,
            score_name,
            value,
        })
    }
}

impl ClientboundPacket for ScoreboardScore {
    fn state(&self) -> ConnectionState {
        ConnectionState::Play
    }
    fn packet_id(&self) -> i32 {
        PACKET_ID
    }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        string::write(&self.item_name, writer)?;
        varint::write(self.action, writer)?;
        string::write(&self.score_name, writer)?;
        if let Some(v) = self.value {
            varint::write(v, writer)?;
        }
        Ok(())
    }
}
