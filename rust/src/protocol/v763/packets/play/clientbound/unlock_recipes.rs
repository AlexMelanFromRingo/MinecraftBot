//! Packet `unlock_recipes` (play/clientbound). Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot,
    string_codec as string, varint, varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x3D;

#[derive(Debug, Clone, PartialEq, Default)]
pub struct UnlockRecipes {
    pub action: i32,
    pub crafting_book_open: bool,
    pub crafting_book_filter_active: bool,
    pub smelting_book_open: bool,
    pub smelting_book_filter_active: bool,
    pub blast_furnace_book_open: bool,
    pub blast_furnace_book_filter_active: bool,
    pub smoker_book_open: bool,
    pub smoker_book_filter_active: bool,
    pub recipe_ids_1: Vec<String>,
    pub recipe_ids_2: Vec<String>,
}

fn read_bool(reader: &mut BytesReader<'_>) -> Result<bool, ProtocolError> {
    let b = reader.read_exact(1)?[0];
    if b > 1 { return Err(ProtocolError::DecodeError(format!("bool: {}", b))); }
    Ok(b != 0)
}

impl UnlockRecipes {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let action = varint::read(reader)?;
        let crafting_book_open = read_bool(reader)?;
        let crafting_book_filter_active = read_bool(reader)?;
        let smelting_book_open = read_bool(reader)?;
        let smelting_book_filter_active = read_bool(reader)?;
        let blast_furnace_book_open = read_bool(reader)?;
        let blast_furnace_book_filter_active = read_bool(reader)?;
        let smoker_book_open = read_bool(reader)?;
        let smoker_book_filter_active = read_bool(reader)?;
        let n1 = varint::read(reader)? as usize;
        let mut recipe_ids_1 = Vec::with_capacity(n1);
        for _ in 0..n1 { recipe_ids_1.push(identifier::read(reader)?); }
        let mut recipe_ids_2 = Vec::new();
        if action == 0 {
            let n2 = varint::read(reader)? as usize;
            recipe_ids_2.reserve(n2);
            for _ in 0..n2 { recipe_ids_2.push(identifier::read(reader)?); }
        }
        Ok(Self {
            action, crafting_book_open, crafting_book_filter_active,
            smelting_book_open, smelting_book_filter_active,
            blast_furnace_book_open, blast_furnace_book_filter_active,
            smoker_book_open, smoker_book_filter_active,
            recipe_ids_1, recipe_ids_2,
        })
    }
}

impl ClientboundPacket for UnlockRecipes {
    fn state(&self) -> ConnectionState { ConnectionState::Play }
    fn packet_id(&self) -> i32 { PACKET_ID }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        varint::write(self.action, writer)?;
        for b in [self.crafting_book_open, self.crafting_book_filter_active,
                  self.smelting_book_open, self.smelting_book_filter_active,
                  self.blast_furnace_book_open, self.blast_furnace_book_filter_active,
                  self.smoker_book_open, self.smoker_book_filter_active] {
            writer.write_all(&[if b { 1 } else { 0 }])?;
        }
        varint::write(self.recipe_ids_1.len() as i32, writer)?;
        for r in &self.recipe_ids_1 { identifier::write(r, writer)?; }
        if self.action == 0 {
            varint::write(self.recipe_ids_2.len() as i32, writer)?;
            for r in &self.recipe_ids_2 { identifier::write(r, writer)?; }
        }
        Ok(())
    }
}
