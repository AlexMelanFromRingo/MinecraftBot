//! Packet `sound_effect`. Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec as string, varint,
    varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x62;

#[derive(Debug, Clone, PartialEq, Default)]
pub struct SoundEffect {
    pub sound_id: i32,
    pub custom_sound: Option<String>,
    pub custom_range: Option<f32>,
    pub sound_category: i32,
    pub x: i32,
    pub y: i32,
    pub z: i32,
    pub volume: f32,
    pub pitch: f32,
    pub seed: i64,
}
impl SoundEffect {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let sound_id = varint::read(reader)?;
        let (custom_sound, custom_range) = if sound_id == 0 {
            let cs = Some(identifier::read(reader)?);
            let p = reader.read_exact(1)?[0];
            let cr = match p {
                0 => None,
                1 => {
                    let b = reader.read_exact(4)?;
                    Some(f32::from_be_bytes([b[0], b[1], b[2], b[3]]))
                }
                o => return Err(ProtocolError::DecodeError(format!("range: {}", o))),
            };
            (cs, cr)
        } else {
            (None, None)
        };
        let sound_category = varint::read(reader)?;
        let b = reader.read_exact(12)?;
        let x = i32::from_be_bytes([b[0], b[1], b[2], b[3]]);
        let y = i32::from_be_bytes([b[4], b[5], b[6], b[7]]);
        let z = i32::from_be_bytes([b[8], b[9], b[10], b[11]]);
        let vb = reader.read_exact(8)?;
        let volume = f32::from_be_bytes([vb[0], vb[1], vb[2], vb[3]]);
        let pitch = f32::from_be_bytes([vb[4], vb[5], vb[6], vb[7]]);
        let sb = reader.read_exact(8)?;
        let seed = i64::from_be_bytes([sb[0], sb[1], sb[2], sb[3], sb[4], sb[5], sb[6], sb[7]]);
        Ok(Self {
            sound_id,
            custom_sound,
            custom_range,
            sound_category,
            x,
            y,
            z,
            volume,
            pitch,
            seed,
        })
    }
}
impl ClientboundPacket for SoundEffect {
    fn state(&self) -> ConnectionState {
        ConnectionState::Play
    }
    fn packet_id(&self) -> i32 {
        PACKET_ID
    }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        varint::write(self.sound_id, writer)?;
        if self.sound_id == 0 {
            identifier::write(self.custom_sound.as_deref().unwrap_or(""), writer)?;
            match self.custom_range {
                None => writer.write_all(&[0])?,
                Some(r) => {
                    writer.write_all(&[1])?;
                    writer.write_all(&r.to_be_bytes())?;
                }
            }
        }
        varint::write(self.sound_category, writer)?;
        writer.write_all(&self.x.to_be_bytes())?;
        writer.write_all(&self.y.to_be_bytes())?;
        writer.write_all(&self.z.to_be_bytes())?;
        writer.write_all(&self.volume.to_be_bytes())?;
        writer.write_all(&self.pitch.to_be_bytes())?;
        writer.write_all(&self.seed.to_be_bytes())?;
        Ok(())
    }
}
