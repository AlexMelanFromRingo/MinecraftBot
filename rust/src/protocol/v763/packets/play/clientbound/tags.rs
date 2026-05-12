//! Packet `tags` (play/clientbound). Hand-written.

use crate::codec::uuid_codec::{self as uuid_c, Uuid};
use crate::codec::{
    bitset, chat_component, identifier, nbt, position, slot,
    string_codec as string, varint, varlong, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

pub const PACKET_ID: i32 = 0x6E;

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct TagsEntry {
    pub tag_name: String,
    pub ids: Vec<i32>,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct TagsGroup {
    pub registry: String,
    pub tags: Vec<TagsEntry>,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Tags {
    pub groups: Vec<TagsGroup>,
}

impl Tags {
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let n = varint::read(reader)? as usize;
        let mut groups = Vec::with_capacity(n);
        for _ in 0..n {
            let registry = identifier::read(reader)?;
            let m = varint::read(reader)? as usize;
            let mut tags = Vec::with_capacity(m);
            for _ in 0..m {
                let tag_name = identifier::read(reader)?;
                let k = varint::read(reader)? as usize;
                let mut ids = Vec::with_capacity(k);
                for _ in 0..k { ids.push(varint::read(reader)?); }
                tags.push(TagsEntry { tag_name, ids });
            }
            groups.push(TagsGroup { registry, tags });
        }
        Ok(Self { groups })
    }
}

impl ClientboundPacket for Tags {
    fn state(&self) -> ConnectionState { ConnectionState::Play }
    fn packet_id(&self) -> i32 { PACKET_ID }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        varint::write(self.groups.len() as i32, writer)?;
        for g in &self.groups {
            identifier::write(&g.registry, writer)?;
            varint::write(g.tags.len() as i32, writer)?;
            for t in &g.tags {
                identifier::write(&t.tag_name, writer)?;
                varint::write(t.ids.len() as i32, writer)?;
                for id in &t.ids { varint::write(*id, writer)?; }
            }
        }
        Ok(())
    }
}
