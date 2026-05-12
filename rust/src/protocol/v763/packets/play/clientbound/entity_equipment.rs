//! Packet `entity_equipment` (play/clientbound). Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot,
    string_codec as string, varint, varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x55;

#[derive(Debug, Clone, PartialEq, Default)]
pub struct EquipmentEntry {
    pub slot: i8,
    pub item: Option<slot::SlotData>,
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct EntityEquipment {
    pub entity_id: i32,
    pub equipments: Vec<EquipmentEntry>,
}

impl EntityEquipment {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let entity_id = varint::read(reader)?;
        let mut equipments = Vec::new();
        loop {
            let raw_slot = reader.read_exact(1)?[0];
            let more = raw_slot & 0x80 != 0;
            let mut s = (raw_slot & 0x7F) as i32;
            if s & 0x40 != 0 { s -= 0x80; }
            let item = slot::read(reader)?;
            equipments.push(EquipmentEntry { slot: s as i8, item });
            if !more { break; }
        }
        Ok(Self { entity_id, equipments })
    }
}

impl ClientboundPacket for EntityEquipment {
    fn state(&self) -> ConnectionState { ConnectionState::Play }
    fn packet_id(&self) -> i32 { PACKET_ID }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        varint::write(self.entity_id, writer)?;
        for (i, e) in self.equipments.iter().enumerate() {
            let more = i + 1 < self.equipments.len();
            let mut raw = (e.slot as u8) & 0x7F;
            if more { raw |= 0x80; }
            writer.write_all(&[raw])?;
            slot::write(e.item.as_ref(), writer)?;
        }
        Ok(())
    }
}
