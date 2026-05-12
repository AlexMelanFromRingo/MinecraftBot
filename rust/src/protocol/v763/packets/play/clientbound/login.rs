//! Packet `login`. Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec as string, varint,
    varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x28;

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct DeathLocation {
    pub dimension_name: String,
    pub location: (i32, i32, i32),
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct Login {
    pub entity_id: i32,
    pub is_hardcore: bool,
    pub game_mode: u8,
    pub previous_game_mode: i8,
    pub world_names: Vec<String>,
    pub dimension_codec: Option<nbt::NbtTag>,
    pub world_type: String,
    pub world_name: String,
    pub hashed_seed: i64,
    pub max_players: i32,
    pub view_distance: i32,
    pub simulation_distance: i32,
    pub reduced_debug_info: bool,
    pub enable_respawn_screen: bool,
    pub is_debug: bool,
    pub is_flat: bool,
    pub death_location: Option<DeathLocation>,
    pub portal_cooldown: i32,
}

fn read_bool(reader: &mut BytesReader<'_>) -> Result<bool, ProtocolError> {
    let b = reader.read_exact(1)?[0];
    if b > 1 {
        return Err(ProtocolError::DecodeError(format!("bool: {}", b)));
    }
    Ok(b != 0)
}

impl Login {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let eb = reader.read_exact(4)?;
        let entity_id = i32::from_be_bytes([eb[0], eb[1], eb[2], eb[3]]);
        let is_hardcore = read_bool(reader)?;
        let game_mode = reader.read_exact(1)?[0];
        let previous_game_mode = reader.read_exact(1)?[0] as i8;
        let n_worlds = varint::read(reader)? as usize;
        let mut world_names = Vec::with_capacity(n_worlds);
        for _ in 0..n_worlds {
            world_names.push(identifier::read(reader)?);
        }
        let dimension_codec = nbt::read(reader)?;
        let world_type = identifier::read(reader)?;
        let world_name = identifier::read(reader)?;
        let hb = reader.read_exact(8)?;
        let hashed_seed =
            i64::from_be_bytes([hb[0], hb[1], hb[2], hb[3], hb[4], hb[5], hb[6], hb[7]]);
        let max_players = varint::read(reader)?;
        let view_distance = varint::read(reader)?;
        let simulation_distance = varint::read(reader)?;
        let reduced_debug_info = read_bool(reader)?;
        let enable_respawn_screen = read_bool(reader)?;
        let is_debug = read_bool(reader)?;
        let is_flat = read_bool(reader)?;
        let has_death = read_bool(reader)?;
        let death_location = if has_death {
            Some(DeathLocation {
                dimension_name: identifier::read(reader)?,
                location: position::read(reader)?,
            })
        } else {
            None
        };
        let portal_cooldown = varint::read(reader)?;
        Ok(Self {
            entity_id,
            is_hardcore,
            game_mode,
            previous_game_mode,
            world_names,
            dimension_codec,
            world_type,
            world_name,
            hashed_seed,
            max_players,
            view_distance,
            simulation_distance,
            reduced_debug_info,
            enable_respawn_screen,
            is_debug,
            is_flat,
            death_location,
            portal_cooldown,
        })
    }
}

impl ClientboundPacket for Login {
    fn state(&self) -> ConnectionState {
        ConnectionState::Play
    }
    fn packet_id(&self) -> i32 {
        PACKET_ID
    }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        writer.write_all(&self.entity_id.to_be_bytes())?;
        writer.write_all(&[if self.is_hardcore { 1 } else { 0 }])?;
        writer.write_all(&[self.game_mode])?;
        writer.write_all(&[self.previous_game_mode as u8])?;
        varint::write(self.world_names.len() as i32, writer)?;
        for w in &self.world_names {
            identifier::write(w, writer)?;
        }
        nbt::write(self.dimension_codec.as_ref(), writer)?;
        identifier::write(&self.world_type, writer)?;
        identifier::write(&self.world_name, writer)?;
        writer.write_all(&self.hashed_seed.to_be_bytes())?;
        varint::write(self.max_players, writer)?;
        varint::write(self.view_distance, writer)?;
        varint::write(self.simulation_distance, writer)?;
        for b in [
            self.reduced_debug_info,
            self.enable_respawn_screen,
            self.is_debug,
            self.is_flat,
        ] {
            writer.write_all(&[if b { 1 } else { 0 }])?;
        }
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
