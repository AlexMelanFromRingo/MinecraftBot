//! Wire framer — length-prefix + optional zlib-threshold compression (T118).
//!
//! Mirrors `python/minecraft_bot/framer.py` byte-for-byte:
//!
//! ```text
//! [varint:packet_length] [packet_length bytes: id_varint + payload]
//! ```
//!
//! When compression is enabled (`compression_threshold >= 0`), each frame's
//! inner payload is prefixed by a `varint:data_length`:
//! - `data_length == 0` → the remainder is the **uncompressed** body
//! - `data_length > 0`  → the remainder is `zlib(body)` of `data_length`
//!   uncompressed bytes
//!
//! The struct is stateful: feed raw socket bytes via [`Framer::feed`] and
//! repeatedly call [`Framer::try_extract`] in a loop until it returns
//! `None`, then await more reads on the socket.

use crate::codec::{varint, BytesReader, BytesWriter, Reader, Writer};
use crate::errors::ProtocolError;

use flate2::read::ZlibDecoder;
use flate2::write::ZlibEncoder;
use flate2::Compression;
use std::io::{Read, Write};

/// Hard cap on a single inbound packet's payload size.
///
/// The protocol caps individual fields; this is a safety net against an
/// oversized length prefix that would otherwise let us allocate
/// unboundedly.
pub const MAX_PACKET_SIZE: usize = 2 * 1024 * 1024; // 2 MiB

/// Stateful packet framer over a single bidirectional stream.
pub struct Framer {
    /// Server-issued zlib threshold. `-1` disables compression entirely.
    pub compression_threshold: i32,
    buf: Vec<u8>,
}

impl Framer {
    /// Construct a framer with compression disabled (`threshold = -1`).
    pub fn new() -> Self {
        Self {
            compression_threshold: -1,
            buf: Vec::new(),
        }
    }

    /// Construct a framer with the given compression threshold.
    pub fn with_compression(threshold: i32) -> Self {
        Self {
            compression_threshold: threshold,
            buf: Vec::new(),
        }
    }

    /// Push raw socket bytes into the internal buffer.
    pub fn feed(&mut self, data: &[u8]) {
        if !data.is_empty() {
            self.buf.extend_from_slice(data);
        }
    }

    /// Currently buffered byte count.
    pub fn buffered_bytes(&self) -> usize {
        self.buf.len()
    }

    /// Try to extract one complete packet body from the buffer.
    ///
    /// Returns `Ok(Some(body))` on success — `body` is `id_varint + payload`,
    /// transparently decompressed when needed. Returns `Ok(None)` when the
    /// buffer doesn't yet hold a complete frame. Returns `Err(...)` on
    /// malformed input.
    pub fn try_extract(&mut self) -> Result<Option<Vec<u8>>, ProtocolError> {
        if self.buf.is_empty() {
            return Ok(None);
        }

        // 1) Outer packet length.
        let (packet_length, length_size) = match try_read_varint(&self.buf)? {
            Some(p) => p,
            None => return Ok(None),
        };
        if packet_length < 0 {
            return Err(ProtocolError::DecodeError(format!(
                "negative packet length: {}",
                packet_length
            )));
        }
        if (packet_length as usize) > MAX_PACKET_SIZE {
            return Err(ProtocolError::DecodeError(format!(
                "packet length {} exceeds MAX_PACKET_SIZE ({})",
                packet_length, MAX_PACKET_SIZE
            )));
        }
        let total = length_size + packet_length as usize;
        if self.buf.len() < total {
            return Ok(None);
        }

        let payload: Vec<u8> = self.buf[length_size..total].to_vec();
        // Drain the consumed bytes.
        self.buf.drain(..total);

        // 2) Compression handling.
        if self.compression_threshold < 0 {
            return Ok(Some(payload));
        }

        let (data_length, inner_size) = match try_read_varint(&payload)? {
            Some(p) => p,
            None => {
                return Err(ProtocolError::DecodeError(
                    "compressed frame missing inner data-length varint".into(),
                ));
            }
        };
        if data_length < 0 {
            return Err(ProtocolError::DecodeError(format!(
                "negative data_length: {}",
                data_length
            )));
        }
        let rest = &payload[inner_size..];
        if data_length == 0 {
            return Ok(Some(rest.to_vec()));
        }
        // data_length > 0 — decompress.
        let mut decoder = ZlibDecoder::new(rest);
        let mut decompressed = Vec::with_capacity(data_length as usize);
        decoder
            .read_to_end(&mut decompressed)
            .map_err(|e| ProtocolError::DecodeError(format!("zlib decompress failed: {}", e)))?;
        if decompressed.len() != data_length as usize {
            return Err(ProtocolError::DecodeError(format!(
                "decompressed size {} != declared {}",
                decompressed.len(),
                data_length
            )));
        }
        Ok(Some(decompressed))
    }

    /// Frame a packet body (`id_varint + payload`) for transmission.
    ///
    /// When compression is enabled and `body.len() >= threshold`, body is
    /// zlib-compressed; otherwise the inner data-length is 0 and the body
    /// passes through.
    pub fn encode(&self, body: &[u8]) -> Result<Vec<u8>, ProtocolError> {
        if self.compression_threshold < 0 {
            let mut len_w = BytesWriter::new();
            varint::write(body.len() as i32, &mut len_w)?;
            let mut out = len_w.into_bytes();
            out.extend_from_slice(body);
            return Ok(out);
        }

        // Compression enabled.
        let inner: Vec<u8> = if body.len() >= self.compression_threshold as usize {
            let mut encoder = ZlibEncoder::new(Vec::new(), Compression::default());
            encoder
                .write_all(body)
                .map_err(|e| ProtocolError::DecodeError(format!("zlib compress write: {}", e)))?;
            let compressed = encoder
                .finish()
                .map_err(|e| ProtocolError::DecodeError(format!("zlib compress finish: {}", e)))?;
            let mut header = BytesWriter::new();
            varint::write(body.len() as i32, &mut header)?;
            let mut inner = header.into_bytes();
            inner.extend_from_slice(&compressed);
            inner
        } else {
            let mut header = BytesWriter::new();
            varint::write(0, &mut header)?;
            let mut inner = header.into_bytes();
            inner.extend_from_slice(body);
            inner
        };
        let mut outer = BytesWriter::new();
        varint::write(inner.len() as i32, &mut outer)?;
        let mut out = outer.into_bytes();
        out.extend_from_slice(&inner);
        Ok(out)
    }
}

impl Default for Framer {
    fn default() -> Self {
        Self::new()
    }
}

/// Try to read a VarInt off the front of `buf`.
///
/// Returns `Ok(Some((value, bytes_consumed)))` on a complete varint,
/// `Ok(None)` if more bytes are needed, or `Err` if the encoding runs
/// past 5 bytes.
fn try_read_varint(buf: &[u8]) -> Result<Option<(i32, usize)>, ProtocolError> {
    let mut result: u32 = 0;
    let limit = buf.len().min(5);
    for (i, b) in buf.iter().take(limit).enumerate() {
        result |= ((*b as u32) & 0x7F) << (7 * i);
        if (*b & 0x80) == 0 {
            return Ok(Some((result as i32, i + 1)));
        }
    }
    if buf.len() < 5 {
        return Ok(None);
    }
    Err(ProtocolError::DecodeError(
        "varint exceeded 5-byte maximum".into(),
    ))
}

// Use the codec's varint module so we keep encode/decode paths identical.
// `BytesReader` import is unused here but kept for symmetry with the Python file.
#[allow(dead_code)]
fn _silence_reader_lint(_r: BytesReader<'_>) {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip_simple_body() {
        let body = b"\x00\x01\x02hello";
        let f = Framer::new();
        let framed = f.encode(body).unwrap();
        let mut g = Framer::new();
        g.feed(&framed);
        let extracted = g.try_extract().unwrap().expect("frame ready");
        assert_eq!(&extracted, body);
        assert!(
            g.try_extract().unwrap().is_none(),
            "buffer should be drained"
        );
    }

    #[test]
    fn partial_frame_returns_none() {
        let body = b"\x10\x20\x30\x40";
        let f = Framer::new();
        let framed = f.encode(body).unwrap();
        let mut g = Framer::new();
        g.feed(&framed[..1]); // varint length only
        assert!(g.try_extract().unwrap().is_none());
        g.feed(&framed[1..framed.len() - 1]);
        assert!(g.try_extract().unwrap().is_none()); // still 1 byte short
        g.feed(&framed[framed.len() - 1..]);
        assert_eq!(g.try_extract().unwrap().unwrap(), body);
    }

    #[test]
    fn round_trip_with_compression_above_threshold() {
        // Body large enough that compression activates (threshold=4).
        let body: Vec<u8> = (0..50u8).cycle().take(200).collect();
        let f = Framer::with_compression(4);
        let framed = f.encode(&body).unwrap();
        let mut g = Framer::with_compression(4);
        g.feed(&framed);
        let extracted = g.try_extract().unwrap().expect("frame ready");
        assert_eq!(extracted, body);
    }

    #[test]
    fn round_trip_with_compression_below_threshold() {
        let body = b"short";
        let f = Framer::with_compression(100);
        let framed = f.encode(body).unwrap();
        let mut g = Framer::with_compression(100);
        g.feed(&framed);
        let extracted = g.try_extract().unwrap().expect("frame ready");
        assert_eq!(&extracted, body);
    }

    #[test]
    fn over_size_packet_rejects() {
        // A varint length of 0xFFFFFFFF (~4 GiB) should fail before allocation.
        let mut g = Framer::new();
        g.feed(&[0xFF, 0xFF, 0xFF, 0xFF, 0x0F]); // varint i32::MAX
        assert!(g.try_extract().is_err());
    }
}
