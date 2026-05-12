//! Packet `entity_update_attributes` (play/clientbound). Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec as string, varint,
    varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x6A;

#[derive(Debug, Clone, PartialEq, Default)]
pub struct Modifier {
    pub uuid: Uuid,
    pub amount: f64,
    pub operation: i8,
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct Attribute {
    pub key: String,
    pub value: f64,
    pub modifiers: Vec<Modifier>,
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct EntityUpdateAttributes {
    pub entity_id: i32,
    pub attributes: Vec<Attribute>,
}

impl EntityUpdateAttributes {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let entity_id = varint::read(reader)?;
        let n = varint::read(reader)? as usize;
        let mut attributes = Vec::with_capacity(n);
        for _ in 0..n {
            let key = identifier::read(reader)?;
            let vb = reader.read_exact(8)?;
            let value =
                f64::from_be_bytes([vb[0], vb[1], vb[2], vb[3], vb[4], vb[5], vb[6], vb[7]]);
            let m = varint::read(reader)? as usize;
            let mut modifiers = Vec::with_capacity(m);
            for _ in 0..m {
                let uuid = uuid_c::read(reader)?;
                let ab = reader.read_exact(8)?;
                let amount =
                    f64::from_be_bytes([ab[0], ab[1], ab[2], ab[3], ab[4], ab[5], ab[6], ab[7]]);
                let operation = reader.read_exact(1)?[0] as i8;
                modifiers.push(Modifier {
                    uuid,
                    amount,
                    operation,
                });
            }
            attributes.push(Attribute {
                key,
                value,
                modifiers,
            });
        }
        Ok(Self {
            entity_id,
            attributes,
        })
    }
}

impl ClientboundPacket for EntityUpdateAttributes {
    fn state(&self) -> ConnectionState {
        ConnectionState::Play
    }
    fn packet_id(&self) -> i32 {
        PACKET_ID
    }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        varint::write(self.entity_id, writer)?;
        varint::write(self.attributes.len() as i32, writer)?;
        for a in &self.attributes {
            identifier::write(&a.key, writer)?;
            writer.write_all(&a.value.to_be_bytes())?;
            varint::write(a.modifiers.len() as i32, writer)?;
            for m in &a.modifiers {
                uuid_c::write(&m.uuid, writer)?;
                writer.write_all(&m.amount.to_be_bytes())?;
                writer.write_all(&[m.operation as u8])?;
            }
        }
        Ok(())
    }
}
