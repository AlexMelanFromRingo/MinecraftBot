//! Packet `tab_complete` (play/clientbound). Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec as string, varint,
    varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x0F;

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct TabCompleteMatch {
    pub r#match: String,
    pub tooltip: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct TabComplete {
    pub transaction_id: i32,
    pub start: i32,
    pub length: i32,
    pub matches: Vec<TabCompleteMatch>,
}

impl TabComplete {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let transaction_id = varint::read(reader)?;
        let start = varint::read(reader)?;
        let length = varint::read(reader)?;
        let n = varint::read(reader)? as usize;
        let mut matches = Vec::with_capacity(n);
        for _ in 0..n {
            let m = string::read(reader)?;
            let p = reader.read_exact(1)?[0];
            let tooltip = match p {
                0 => None,
                1 => Some(string::read(reader)?),
                other => return Err(ProtocolError::DecodeError(format!("tooltip: {}", other))),
            };
            matches.push(TabCompleteMatch {
                r#match: m,
                tooltip,
            });
        }
        Ok(Self {
            transaction_id,
            start,
            length,
            matches,
        })
    }
}

impl ClientboundPacket for TabComplete {
    fn state(&self) -> ConnectionState {
        ConnectionState::Play
    }
    fn packet_id(&self) -> i32 {
        PACKET_ID
    }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        varint::write(self.transaction_id, writer)?;
        varint::write(self.start, writer)?;
        varint::write(self.length, writer)?;
        varint::write(self.matches.len() as i32, writer)?;
        for m in &self.matches {
            string::write(&m.r#match, writer)?;
            match &m.tooltip {
                None => writer.write_all(&[0])?,
                Some(t) => {
                    writer.write_all(&[1])?;
                    string::write(t, writer)?;
                }
            }
        }
        Ok(())
    }
}
