//! Packet `window_click` (play/serverbound). Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec as string, varint,
    varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ServerboundPacket;

pub const PACKET_ID: i32 = 0x0B;

#[derive(Debug, Clone, PartialEq, Default)]
pub struct ChangedSlot {
    pub slot_index: i16,
    pub item: Option<slot::SlotData>,
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct WindowClick {
    pub window_id: u8,
    pub state_id: i32,
    pub slot_index: i16,
    pub mouse_button: i8,
    pub mode: i32,
    pub changed_slots: Vec<ChangedSlot>,
    pub carried_item: Option<slot::SlotData>,
}

impl WindowClick {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let window_id = reader.read_exact(1)?[0];
        let state_id = varint::read(reader)?;
        let sb = reader.read_exact(2)?;
        let slot_index = i16::from_be_bytes([sb[0], sb[1]]);
        let mouse_button = reader.read_exact(1)?[0] as i8;
        let mode = varint::read(reader)?;
        let n = varint::read(reader)? as usize;
        let mut changed_slots = Vec::with_capacity(n);
        for _ in 0..n {
            let sb = reader.read_exact(2)?;
            let s = i16::from_be_bytes([sb[0], sb[1]]);
            let item = slot::read(reader)?;
            changed_slots.push(ChangedSlot {
                slot_index: s,
                item,
            });
        }
        let carried_item = slot::read(reader)?;
        Ok(Self {
            window_id,
            state_id,
            slot_index,
            mouse_button,
            mode,
            changed_slots,
            carried_item,
        })
    }
}

impl ServerboundPacket for WindowClick {
    fn state(&self) -> ConnectionState {
        ConnectionState::Play
    }
    fn packet_id(&self) -> i32 {
        PACKET_ID
    }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        writer.write_all(&[self.window_id])?;
        varint::write(self.state_id, writer)?;
        writer.write_all(&self.slot_index.to_be_bytes())?;
        writer.write_all(&[self.mouse_button as u8])?;
        varint::write(self.mode, writer)?;
        varint::write(self.changed_slots.len() as i32, writer)?;
        for c in &self.changed_slots {
            writer.write_all(&c.slot_index.to_be_bytes())?;
            slot::write(c.item.as_ref(), writer)?;
        }
        slot::write(self.carried_item.as_ref(), writer)?;
        Ok(())
    }
}
