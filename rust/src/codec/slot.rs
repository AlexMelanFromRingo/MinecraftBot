//! Slot codec — inventory item-stack data.

use crate::codec::{Reader, Writer, nbt, varint};
use crate::errors::ProtocolError;

/// Populated inventory slot.
#[derive(Debug, Clone, PartialEq)]
pub struct SlotData {
    /// Numeric item registry id.
    pub item_id: i32,
    /// Stack count (i8 range).
    pub count: i8,
    /// Optional NBT tag.
    pub tag: Option<nbt::NbtTag>,
}

/// Decode a slot. Returns `None` when the slot is empty (`present = 0`).
pub fn read<R: Reader + ?Sized>(reader: &mut R) -> Result<Option<SlotData>, ProtocolError> {
    let present = reader.read_exact(1)?[0];
    match present {
        0 => Ok(None),
        1 => {
            let item_id = varint::read(reader)?;
            let count = reader.read_exact(1)?[0] as i8;
            let tag = nbt::read(reader)?;
            Ok(Some(SlotData { item_id, count, tag }))
        }
        other => Err(ProtocolError::EncodeError(format!(
            "slot.present: {other} (expected 0 or 1)"
        ))),
    }
}

/// Encode an `Option<SlotData>` as a Slot.
pub fn write<W: Writer + ?Sized>(
    value: Option<&SlotData>,
    writer: &mut W,
) -> Result<(), ProtocolError> {
    match value {
        None => writer.write_all(&[0]),
        Some(s) => {
            writer.write_all(&[1])?;
            varint::write(s.item_id, writer)?;
            writer.write_all(&(s.count as u8).to_be_bytes())?;
            nbt::write(s.tag.as_ref(), writer)
        }
    }
}
