//! Packet `success` (login/clientbound, id 0x02). Hand-written.

use crate::codec::uuid_codec::Uuid;
use crate::codec::{
    string_codec as string, uuid_codec as uuid_c, varint, BytesReader, BytesWriter, Reader, Writer,
};
use crate::errors::ProtocolError;
use crate::protocol::v763::states::ConnectionState;
use crate::protocol::v763::ClientboundPacket;

/// Numeric packet id within `(Login, Clientbound)`.
pub const PACKET_ID: i32 = 0x02;

/// One profile property.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Property {
    /// Property name.
    pub name: String,
    /// JSON-encoded value.
    pub value: String,
    /// Optional Mojang signature.
    pub signature: Option<String>,
}

/// Server's login-success packet.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Success {
    /// Resolved player UUID.
    pub uuid: Uuid,
    /// Display name.
    pub username: String,
    /// Profile properties (may be empty in offline mode).
    pub properties: Vec<Property>,
}

impl Success {
    /// Decode from `reader`.
    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {
        let uuid = uuid_c::read(reader)?;
        let username = string::read(reader)?;
        let n_props = varint::read(reader)? as usize;
        let mut properties = Vec::with_capacity(n_props);
        for _ in 0..n_props {
            let name = string::read(reader)?;
            let value = string::read(reader)?;
            let signed = reader.read_exact(1)?[0];
            let signature = match signed {
                0 => None,
                1 => Some(string::read(reader)?),
                other => {
                    return Err(ProtocolError::DecodeError(format!(
                        "success.properties.signature.present: {}",
                        other
                    )))
                }
            };
            properties.push(Property {
                name,
                value,
                signature,
            });
        }
        Ok(Self {
            uuid,
            username,
            properties,
        })
    }
}

impl ClientboundPacket for Success {
    fn state(&self) -> ConnectionState {
        ConnectionState::Login
    }
    fn packet_id(&self) -> i32 {
        PACKET_ID
    }
    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {
        uuid_c::write(&self.uuid, writer)?;
        string::write(&self.username, writer)?;
        varint::write(self.properties.len() as i32, writer)?;
        for prop in &self.properties {
            string::write(&prop.name, writer)?;
            string::write(&prop.value, writer)?;
            match &prop.signature {
                None => writer.write_all(&[0])?,
                Some(s) => {
                    writer.write_all(&[1])?;
                    string::write(s, writer)?;
                }
            }
        }
        Ok(())
    }
}
