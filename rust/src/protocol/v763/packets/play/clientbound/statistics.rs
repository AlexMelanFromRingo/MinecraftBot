//! Packet `statistics` (play/clientbound). Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec as string, varint,
    varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x05;

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct StatisticEntry {
    pub category_id: i32,
    pub statistic_id: i32,
    pub value: i32,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Statistics {
    pub entries: Vec<StatisticEntry>,
}

impl Statistics {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let n = varint::read(reader)? as usize;
        let mut entries = Vec::with_capacity(n);
        for _ in 0..n {
            entries.push(StatisticEntry {
                category_id: varint::read(reader)?,
                statistic_id: varint::read(reader)?,
                value: varint::read(reader)?,
            });
        }
        Ok(Self { entries })
    }
}

impl ClientboundPacket for Statistics {
    fn state(&self) -> ConnectionState {
        ConnectionState::Play
    }
    fn packet_id(&self) -> i32 {
        PACKET_ID
    }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        varint::write(self.entries.len() as i32, writer)?;
        for e in &self.entries {
            varint::write(e.category_id, writer)?;
            varint::write(e.statistic_id, writer)?;
            varint::write(e.value, writer)?;
        }
        Ok(())
    }
}
