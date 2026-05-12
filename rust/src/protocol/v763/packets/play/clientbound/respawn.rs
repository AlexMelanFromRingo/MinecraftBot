//! Packet `respawn`. Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot,
    string_codec as string, varint, varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x41;

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct DeathLocation { pub dimension_name: String, pub location: (i32, i32, i32) }

#[derive(Debug, Clone, PartialEq, Default)]
pub struct Respawn {
    pub dimension: String,
    pub world_name: String,
    pub hashed_seed: i64,
    pub game_mode: u8,
    pub previous_game_mode: i8,
    pub is_debug: bool,
    pub is_flat: bool,
    pub copy_metadata: u8,
    pub death_location: Option<DeathLocation>,
    pub portal_cooldown: i32,
}

fn read_bool(reader: &mut BytesReader<'_>) -> Result<bool, ProtocolError> {
    let b = reader.read_exact(1)?[0];
    if b > 1 { return Err(ProtocolError::DecodeError(format!("bool: {}", b))); }
    Ok(b != 0)
}

impl Respawn {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let dimension = identifier::read(reader)?;
        let world_name = identifier::read(reader)?;
        let hb = reader.read_exact(8)?;
        let hashed_seed = i64::from_be_bytes([hb[0],hb[1],hb[2],hb[3],hb[4],hb[5],hb[6],hb[7]]);
        let game_mode = reader.read_exact(1)?[0];
        let previous_game_mode = reader.read_exact(1)?[0] as i8;
        let is_debug = read_bool(reader)?;
        let is_flat = read_bool(reader)?;
        let copy_metadata = reader.read_exact(1)?[0];
        let has_death = read_bool(reader)?;
        let death_location = if has_death {
            Some(DeathLocation {
                dimension_name: identifier::read(reader)?,
                location: position::read(reader)?,
            })
        } else { None };
        let portal_cooldown = varint::read(reader)?;
        Ok(Self { dimension, world_name, hashed_seed, game_mode, previous_game_mode,
                  is_debug, is_flat, copy_metadata, death_location, portal_cooldown })
    }
}

impl ClientboundPacket for Respawn {
    fn state(&self) -> ConnectionState { ConnectionState::Play }
    fn packet_id(&self) -> i32 { PACKET_ID }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        identifier::write(&self.dimension, writer)?;
        identifier::write(&self.world_name, writer)?;
        writer.write_all(&self.hashed_seed.to_be_bytes())?;
        writer.write_all(&[self.game_mode])?;
        writer.write_all(&[self.previous_game_mode as u8])?;
        writer.write_all(&[if self.is_debug { 1 } else { 0 }])?;
        writer.write_all(&[if self.is_flat { 1 } else { 0 }])?;
        writer.write_all(&[self.copy_metadata])?;
        match &self.death_location {
            None => writer.write_all(&[0])?,
            Some(d) => {
                writer.write_all(&[1])?;
                identifier::write(&d.dimension_name, writer)?;
                position::write(&d.location, writer)?;
            }
        }
        varint::write(self.portal_cooldown, writer)?;
        Ok(())
    }
}
