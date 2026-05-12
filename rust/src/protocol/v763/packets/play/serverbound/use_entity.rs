//! Packet `use_entity` (play/serverbound). Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot,
    string_codec as string, varint, varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ServerboundPacket;

pub const PACKET_ID: i32 = 0x10;

#[derive(Debug, Clone, PartialEq, Default)]
pub struct UseEntity {
    pub target: i32,
    pub mouse: i32,
    pub x: Option<f32>,
    pub y: Option<f32>,
    pub z: Option<f32>,
    pub hand: Option<i32>,
    pub sneaking: bool,
}

impl UseEntity {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let target = varint::read(reader)?;
        let mouse = varint::read(reader)?;
        let (mut x, mut y, mut z) = (None, None, None);
        let mut hand = None;
        if mouse == 2 {
            let b = reader.read_exact(12)?;
            x = Some(f32::from_be_bytes([b[0],b[1],b[2],b[3]]));
            y = Some(f32::from_be_bytes([b[4],b[5],b[6],b[7]]));
            z = Some(f32::from_be_bytes([b[8],b[9],b[10],b[11]]));
        }
        if mouse == 0 || mouse == 2 { hand = Some(varint::read(reader)?); }
        let bn = reader.read_exact(1)?[0];
        if bn > 1 { return Err(ProtocolError::DecodeError(format!("sneaking: {}", bn))); }
        Ok(Self { target, mouse, x, y, z, hand, sneaking: bn != 0 })
    }
}

impl ServerboundPacket for UseEntity {
    fn state(&self) -> ConnectionState { ConnectionState::Play }
    fn packet_id(&self) -> i32 { PACKET_ID }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        varint::write(self.target, writer)?;
        varint::write(self.mouse, writer)?;
        if let (Some(x), Some(y), Some(z)) = (self.x, self.y, self.z) {
            writer.write_all(&x.to_be_bytes())?;
            writer.write_all(&y.to_be_bytes())?;
            writer.write_all(&z.to_be_bytes())?;
        }
        if let Some(h) = self.hand { varint::write(h, writer)?; }
        writer.write_all(&[if self.sneaking { 1 } else { 0 }])?;
        Ok(())
    }
}
