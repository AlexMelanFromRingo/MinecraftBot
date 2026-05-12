//! NBT codec — Named Binary Tag, Java Edition. Mirrors Python `codec/nbt.py`.

use crate::codec::{Reader, Writer};
use crate::errors::ProtocolError;

/// Tag type bytes.
pub const TAG_END: u8 = 0;
/// TAG_Byte
pub const TAG_BYTE: u8 = 1;
/// TAG_Short
pub const TAG_SHORT: u8 = 2;
/// TAG_Int
pub const TAG_INT: u8 = 3;
/// TAG_Long
pub const TAG_LONG: u8 = 4;
/// TAG_Float
pub const TAG_FLOAT: u8 = 5;
/// TAG_Double
pub const TAG_DOUBLE: u8 = 6;
/// TAG_Byte_Array
pub const TAG_BYTE_ARRAY: u8 = 7;
/// TAG_String
pub const TAG_STRING: u8 = 8;
/// TAG_List
pub const TAG_LIST: u8 = 9;
/// TAG_Compound
pub const TAG_COMPOUND: u8 = 10;
/// TAG_Int_Array
pub const TAG_INT_ARRAY: u8 = 11;
/// TAG_Long_Array
pub const TAG_LONG_ARRAY: u8 = 12;

/// One NBT tag (recursive).
#[derive(Debug, Clone, PartialEq)]
pub enum NbtTag {
    /// i8
    Byte(i8),
    /// i16
    Short(i16),
    /// i32
    Int(i32),
    /// i64
    Long(i64),
    /// f32
    Float(f32),
    /// f64
    Double(f64),
    /// signed-byte array
    ByteArray(Vec<i8>),
    /// String
    String(String),
    /// Homogeneous list (element_type, items); empty list uses TAG_END as marker.
    List {
        /// Wire type byte of every element (TAG_BYTE, TAG_INT, ...).
        element_type: u8,
        /// The list elements; all share `element_type`.
        items: Vec<NbtTag>,
    },
    /// ordered (name, value) pairs
    Compound(Vec<(String, NbtTag)>),
    /// i32 array
    IntArray(Vec<i32>),
    /// i64 array
    LongArray(Vec<i64>),
}

/// Read a network-NBT-style 2-byte big-endian length-prefixed UTF-8 string.
fn read_nbt_string<R: Reader + ?Sized>(reader: &mut R) -> Result<String, ProtocolError> {
    let lb = reader.read_exact(2)?;
    let n = u16::from_be_bytes([lb[0], lb[1]]) as usize;
    let raw = reader.read_exact(n)?.to_vec();
    String::from_utf8(raw).map_err(|e| ProtocolError::MalformedNbt(format!("non-utf-8: {e}")))
}

fn write_nbt_string<W: Writer + ?Sized>(s: &str, writer: &mut W) -> Result<(), ProtocolError> {
    let raw = s.as_bytes();
    if raw.len() > 0xFFFF {
        return Err(ProtocolError::EncodeError(format!(
            "nbt.string too long: {}",
            raw.len()
        )));
    }
    writer.write_all(&(raw.len() as u16).to_be_bytes())?;
    writer.write_all(raw)
}

fn tag_type_for(tag: &NbtTag) -> u8 {
    match tag {
        NbtTag::Byte(_) => TAG_BYTE,
        NbtTag::Short(_) => TAG_SHORT,
        NbtTag::Int(_) => TAG_INT,
        NbtTag::Long(_) => TAG_LONG,
        NbtTag::Float(_) => TAG_FLOAT,
        NbtTag::Double(_) => TAG_DOUBLE,
        NbtTag::ByteArray(_) => TAG_BYTE_ARRAY,
        NbtTag::String(_) => TAG_STRING,
        NbtTag::List { .. } => TAG_LIST,
        NbtTag::Compound(_) => TAG_COMPOUND,
        NbtTag::IntArray(_) => TAG_INT_ARRAY,
        NbtTag::LongArray(_) => TAG_LONG_ARRAY,
    }
}

fn read_payload<R: Reader + ?Sized>(tag_type: u8, reader: &mut R) -> Result<NbtTag, ProtocolError> {
    Ok(match tag_type {
        TAG_BYTE => NbtTag::Byte(reader.read_exact(1)?[0] as i8),
        TAG_SHORT => {
            let b = reader.read_exact(2)?;
            NbtTag::Short(i16::from_be_bytes([b[0], b[1]]))
        }
        TAG_INT => {
            let b = reader.read_exact(4)?;
            NbtTag::Int(i32::from_be_bytes([b[0], b[1], b[2], b[3]]))
        }
        TAG_LONG => {
            let b = reader.read_exact(8)?;
            let mut buf = [0u8; 8];
            buf.copy_from_slice(b);
            NbtTag::Long(i64::from_be_bytes(buf))
        }
        TAG_FLOAT => {
            let b = reader.read_exact(4)?;
            NbtTag::Float(f32::from_be_bytes([b[0], b[1], b[2], b[3]]))
        }
        TAG_DOUBLE => {
            let b = reader.read_exact(8)?;
            let mut buf = [0u8; 8];
            buf.copy_from_slice(b);
            NbtTag::Double(f64::from_be_bytes(buf))
        }
        TAG_BYTE_ARRAY => {
            let n = i32::from_be_bytes(reader.read_exact(4)?.try_into().unwrap());
            if n < 0 {
                return Err(ProtocolError::MalformedNbt(format!(
                    "negative byte array length: {n}"
                )));
            }
            let raw = reader.read_exact(n as usize)?;
            NbtTag::ByteArray(raw.iter().map(|b| *b as i8).collect())
        }
        TAG_STRING => NbtTag::String(read_nbt_string(reader)?),
        TAG_LIST => {
            let elem = reader.read_exact(1)?[0];
            let n = i32::from_be_bytes(reader.read_exact(4)?.try_into().unwrap());
            if n < 0 {
                return Err(ProtocolError::MalformedNbt(format!(
                    "negative list count: {n}"
                )));
            }
            if n == 0 && elem == TAG_END {
                NbtTag::List {
                    element_type: TAG_END,
                    items: vec![],
                }
            } else if elem == TAG_END {
                return Err(ProtocolError::MalformedNbt(
                    "non-empty list with TAG_End element type".into(),
                ));
            } else {
                let mut items = Vec::with_capacity(n as usize);
                for _ in 0..n {
                    items.push(read_payload(elem, reader)?);
                }
                NbtTag::List {
                    element_type: elem,
                    items,
                }
            }
        }
        TAG_COMPOUND => {
            let mut items = Vec::new();
            loop {
                let child_type = reader.read_exact(1)?[0];
                if child_type == TAG_END {
                    return Ok(NbtTag::Compound(items));
                }
                let child_name = read_nbt_string(reader)?;
                let child_value = read_payload(child_type, reader)?;
                items.push((child_name, child_value));
            }
        }
        TAG_INT_ARRAY => {
            let n = i32::from_be_bytes(reader.read_exact(4)?.try_into().unwrap());
            if n < 0 {
                return Err(ProtocolError::MalformedNbt(format!(
                    "negative int array length: {n}"
                )));
            }
            let mut out = Vec::with_capacity(n as usize);
            for _ in 0..n {
                let b = reader.read_exact(4)?;
                out.push(i32::from_be_bytes([b[0], b[1], b[2], b[3]]));
            }
            NbtTag::IntArray(out)
        }
        TAG_LONG_ARRAY => {
            let n = i32::from_be_bytes(reader.read_exact(4)?.try_into().unwrap());
            if n < 0 {
                return Err(ProtocolError::MalformedNbt(format!(
                    "negative long array length: {n}"
                )));
            }
            let mut out = Vec::with_capacity(n as usize);
            for _ in 0..n {
                let b = reader.read_exact(8)?;
                let mut buf = [0u8; 8];
                buf.copy_from_slice(b);
                out.push(i64::from_be_bytes(buf));
            }
            NbtTag::LongArray(out)
        }
        other => {
            return Err(ProtocolError::MalformedNbt(format!(
                "unknown tag type: {other}"
            )))
        }
    })
}

fn write_payload<W: Writer + ?Sized>(tag: &NbtTag, writer: &mut W) -> Result<(), ProtocolError> {
    match tag {
        NbtTag::Byte(v) => writer.write_all(&[*v as u8]),
        NbtTag::Short(v) => writer.write_all(&v.to_be_bytes()),
        NbtTag::Int(v) => writer.write_all(&v.to_be_bytes()),
        NbtTag::Long(v) => writer.write_all(&v.to_be_bytes()),
        NbtTag::Float(v) => writer.write_all(&v.to_be_bytes()),
        NbtTag::Double(v) => writer.write_all(&v.to_be_bytes()),
        NbtTag::ByteArray(values) => {
            writer.write_all(&(values.len() as i32).to_be_bytes())?;
            let raw: Vec<u8> = values.iter().map(|b| *b as u8).collect();
            writer.write_all(&raw)
        }
        NbtTag::String(s) => write_nbt_string(s, writer),
        NbtTag::List {
            element_type,
            items,
        } => {
            let elem = if items.is_empty() {
                TAG_END
            } else {
                *element_type
            };
            writer.write_all(&[elem])?;
            writer.write_all(&(items.len() as i32).to_be_bytes())?;
            for it in items {
                if tag_type_for(it) != elem {
                    return Err(ProtocolError::EncodeError(
                        "nbt.list: heterogeneous element type".into(),
                    ));
                }
                write_payload(it, writer)?;
            }
            Ok(())
        }
        NbtTag::Compound(items) => {
            for (name, value) in items {
                writer.write_all(&[tag_type_for(value)])?;
                write_nbt_string(name, writer)?;
                write_payload(value, writer)?;
            }
            writer.write_all(&[TAG_END])
        }
        NbtTag::IntArray(values) => {
            writer.write_all(&(values.len() as i32).to_be_bytes())?;
            for v in values {
                writer.write_all(&v.to_be_bytes())?;
            }
            Ok(())
        }
        NbtTag::LongArray(values) => {
            writer.write_all(&(values.len() as i32).to_be_bytes())?;
            for v in values {
                writer.write_all(&v.to_be_bytes())?;
            }
            Ok(())
        }
    }
}

/// Decode a complete NBT document; `None` if the first byte is `TAG_END`.
pub fn read<R: Reader + ?Sized>(reader: &mut R) -> Result<Option<NbtTag>, ProtocolError> {
    let tag_type = reader.read_exact(1)?[0];
    if tag_type == TAG_END {
        return Ok(None);
    }
    if !(TAG_BYTE..=TAG_LONG_ARRAY).contains(&tag_type) {
        return Err(ProtocolError::MalformedNbt(format!(
            "unknown tag type at root: {tag_type}"
        )));
    }
    // Discard root name.
    let _ = read_nbt_string(reader)?;
    Ok(Some(read_payload(tag_type, reader)?))
}

/// Encode a complete NBT document. `None` writes a single TAG_END byte.
pub fn write<W: Writer + ?Sized>(
    value: Option<&NbtTag>,
    writer: &mut W,
) -> Result<(), ProtocolError> {
    write_with_root(value, writer, "")
}

/// Encode with an explicit root name.
pub fn write_with_root<W: Writer + ?Sized>(
    value: Option<&NbtTag>,
    writer: &mut W,
    root_name: &str,
) -> Result<(), ProtocolError> {
    match value {
        None => writer.write_all(&[TAG_END]),
        Some(tag) => {
            writer.write_all(&[tag_type_for(tag)])?;
            write_nbt_string(root_name, writer)?;
            write_payload(tag, writer)
        }
    }
}
