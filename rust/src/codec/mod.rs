//! Primitive codec layer. Mirrors `python/minecraft_bot/codec/`.
//!
//! Each codec lives in its own submodule; this file only exports the
//! [`Reader`] and [`Writer`] traits and the concrete `BytesReader` /
//! `BytesWriter` adaptors.

use crate::errors::ProtocolError;

pub mod bitset;
pub mod chat_component;
pub mod identifier;
pub mod nbt;
pub mod position;
pub mod slot;
pub mod string_codec;
pub mod uuid_codec;
pub mod varint;
pub mod varlong;

/// Synchronous in-memory byte stream reader.
pub trait Reader {
    /// Return the next `n` bytes and advance the cursor.
    ///
    /// Returns [`ProtocolError::IncompleteRead`] if fewer than `n` bytes remain.
    fn read_exact(&mut self, n: usize) -> Result<&[u8], ProtocolError>;

    /// Number of bytes still available.
    fn remaining(&self) -> usize;

    /// Current absolute byte position.
    fn position(&self) -> usize;
}

/// Synchronous in-memory byte stream writer.
pub trait Writer {
    /// Append `b` to the buffer.
    fn write_all(&mut self, b: &[u8]) -> Result<(), ProtocolError>;
}

/// Concrete in-memory `Reader` over a byte slice.
pub struct BytesReader<'a> {
    data: &'a [u8],
    pos: usize,
}

impl<'a> BytesReader<'a> {
    /// Construct a `BytesReader` over `data`.
    pub fn new(data: &'a [u8]) -> Self {
        Self { data, pos: 0 }
    }
}

impl<'a> Reader for BytesReader<'a> {
    fn read_exact(&mut self, n: usize) -> Result<&[u8], ProtocolError> {
        if self.pos + n > self.data.len() {
            return Err(ProtocolError::incomplete(n, self.data.len() - self.pos));
        }
        let out = &self.data[self.pos..self.pos + n];
        self.pos += n;
        Ok(out)
    }

    fn remaining(&self) -> usize {
        self.data.len() - self.pos
    }

    fn position(&self) -> usize {
        self.pos
    }
}

/// Concrete `Writer` backed by a `Vec<u8>`.
#[derive(Default)]
pub struct BytesWriter {
    buf: Vec<u8>,
}

impl BytesWriter {
    /// Construct an empty `BytesWriter`.
    pub fn new() -> Self {
        Self { buf: Vec::new() }
    }

    /// Take ownership of the accumulated bytes.
    pub fn into_bytes(self) -> Vec<u8> {
        self.buf
    }

    /// Borrow the accumulated bytes.
    pub fn as_slice(&self) -> &[u8] {
        &self.buf
    }

    /// Length of the buffer.
    pub fn len(&self) -> usize {
        self.buf.len()
    }

    /// True iff the buffer is empty.
    pub fn is_empty(&self) -> bool {
        self.buf.is_empty()
    }
}

impl Writer for BytesWriter {
    fn write_all(&mut self, b: &[u8]) -> Result<(), ProtocolError> {
        self.buf.extend_from_slice(b);
        Ok(())
    }
}
