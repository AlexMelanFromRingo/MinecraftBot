//! Packet `explosion` (play/clientbound). Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot,
    string_codec as string, varint, varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x1D;

#[derive(Debug, Clone, PartialEq, Default)]
pub struct Explosion {
    pub x: f64,
    pub y: f64,
    pub z: f64,
    pub radius: f32,
    pub affected_block_offsets: Vec<(i8, i8, i8)>,
    pub player_motion_x: f32,
    pub player_motion_y: f32,
    pub player_motion_z: f32,
}

impl Explosion {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let b = reader.read_exact(24)?;
        let x = f64::from_be_bytes([b[0],b[1],b[2],b[3],b[4],b[5],b[6],b[7]]);
        let y = f64::from_be_bytes([b[8],b[9],b[10],b[11],b[12],b[13],b[14],b[15]]);
        let z = f64::from_be_bytes([b[16],b[17],b[18],b[19],b[20],b[21],b[22],b[23]]);
        let rb = reader.read_exact(4)?;
        let radius = f32::from_be_bytes([rb[0],rb[1],rb[2],rb[3]]);
        let n = varint::read(reader)? as usize;
        let mut affected_block_offsets = Vec::with_capacity(n);
        for _ in 0..n {
            let t = reader.read_exact(3)?;
            affected_block_offsets.push((t[0] as i8, t[1] as i8, t[2] as i8));
        }
        let mb = reader.read_exact(12)?;
        let player_motion_x = f32::from_be_bytes([mb[0],mb[1],mb[2],mb[3]]);
        let player_motion_y = f32::from_be_bytes([mb[4],mb[5],mb[6],mb[7]]);
        let player_motion_z = f32::from_be_bytes([mb[8],mb[9],mb[10],mb[11]]);
        Ok(Self { x, y, z, radius, affected_block_offsets, player_motion_x, player_motion_y, player_motion_z })
    }
}

impl ClientboundPacket for Explosion {
    fn state(&self) -> ConnectionState { ConnectionState::Play }
    fn packet_id(&self) -> i32 { PACKET_ID }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        writer.write_all(&self.x.to_be_bytes())?;
        writer.write_all(&self.y.to_be_bytes())?;
        writer.write_all(&self.z.to_be_bytes())?;
        writer.write_all(&self.radius.to_be_bytes())?;
        varint::write(self.affected_block_offsets.len() as i32, writer)?;
        for (a, b, c) in &self.affected_block_offsets {
            writer.write_all(&[*a as u8, *b as u8, *c as u8])?;
        }
        writer.write_all(&self.player_motion_x.to_be_bytes())?;
        writer.write_all(&self.player_motion_y.to_be_bytes())?;
        writer.write_all(&self.player_motion_z.to_be_bytes())?;
        Ok(())
    }
}
