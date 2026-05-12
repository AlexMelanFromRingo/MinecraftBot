//! Packet `damage_event` (play/clientbound). Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec as string, varint,
    varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x18;

#[derive(Debug, Clone, PartialEq, Default)]
pub struct DamageEvent {
    pub entity_id: i32,
    pub source_type_id: i32,
    pub source_cause_id: i32,
    pub source_direct_id: i32,
    pub source_position: Option<(f64, f64, f64)>,
}

impl DamageEvent {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let entity_id = varint::read(reader)?;
        let source_type_id = varint::read(reader)?;
        let source_cause_id = varint::read(reader)?;
        let source_direct_id = varint::read(reader)?;
        let p = reader.read_exact(1)?[0];
        let source_position = match p {
            0 => None,
            1 => {
                let b = reader.read_exact(24)?;
                let x = f64::from_be_bytes([b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7]]);
                let y = f64::from_be_bytes([b[8], b[9], b[10], b[11], b[12], b[13], b[14], b[15]]);
                let z =
                    f64::from_be_bytes([b[16], b[17], b[18], b[19], b[20], b[21], b[22], b[23]]);
                Some((x, y, z))
            }
            other => {
                return Err(ProtocolError::DecodeError(format!(
                    "source_position.present: {}",
                    other
                )))
            }
        };
        Ok(Self {
            entity_id,
            source_type_id,
            source_cause_id,
            source_direct_id,
            source_position,
        })
    }
}

impl ClientboundPacket for DamageEvent {
    fn state(&self) -> ConnectionState {
        ConnectionState::Play
    }
    fn packet_id(&self) -> i32 {
        PACKET_ID
    }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        varint::write(self.entity_id, writer)?;
        varint::write(self.source_type_id, writer)?;
        varint::write(self.source_cause_id, writer)?;
        varint::write(self.source_direct_id, writer)?;
        match self.source_position {
            None => writer.write_all(&[0]),
            Some((x, y, z)) => {
                writer.write_all(&[1])?;
                writer.write_all(&x.to_be_bytes())?;
                writer.write_all(&y.to_be_bytes())?;
                writer.write_all(&z.to_be_bytes())
            }
        }
    }
}
