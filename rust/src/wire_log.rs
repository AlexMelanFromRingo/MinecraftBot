//! Wire-log capture (T125) — bit-identical JSONL with the Python sink.
//!
//! Each session opens a fresh file, writes one ``{"meta": ...}`` header
//! line, then one line per packet. The line format mirrors
//! ``contracts/wire-log-format.md``:
//!
//! ```text
//! {"ts":0.012345,"dir":"rx","state":"login","id":2,"name":"success","raw":"…hex…"}
//! ```
//!
//! Replay (Phase 6 of 001) consumes the same lines.

use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::Instant;

use crate::errors::ProtocolError;
use crate::protocol::v763::states::{ConnectionState, Direction};

/// One captured packet event.
#[derive(Debug, Clone)]
pub struct WireLogEntry {
    /// Seconds since session start.
    pub ts: f64,
    /// rx (clientbound) / tx (serverbound).
    pub direction: Direction,
    /// Connection state when the packet was seen.
    pub state: ConnectionState,
    /// Packet ID within (state, direction).
    pub packet_id: i32,
    /// Optional packet name (snake_case).
    pub name: Option<String>,
    /// Raw payload bytes (lossless).
    pub raw: Vec<u8>,
}

/// Session header — written as the first JSONL line.
#[derive(Debug, Clone)]
pub struct WireLogHeader {
    pub version: i32,
    pub host: String,
    pub port: u16,
    pub username: String,
}

/// File-backed JSONL sink — matches Python's `JsonlFile`.
pub struct JsonlFile {
    path: PathBuf,
    writer: Mutex<BufWriter<File>>,
    started: Instant,
}

impl JsonlFile {
    /// Open ``path`` for write (truncating any existing file). The
    /// header line MUST be written next via ``write_header``.
    pub fn create(path: impl AsRef<Path>) -> Result<Self, ProtocolError> {
        let path = path.as_ref().to_path_buf();
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|e| ProtocolError::DecodeError(format!("mkdirs: {}", e)))?;
        }
        let f =
            File::create(&path).map_err(|e| ProtocolError::DecodeError(format!("open: {}", e)))?;
        Ok(Self {
            path,
            writer: Mutex::new(BufWriter::new(f)),
            started: Instant::now(),
        })
    }

    /// File path being written to.
    pub fn path(&self) -> &Path {
        &self.path
    }

    /// Seconds elapsed since this sink was created (used by the
    /// connection to fill `ts` on each entry).
    pub fn elapsed(&self) -> f64 {
        let d = self.started.elapsed();
        d.as_secs() as f64 + (d.subsec_nanos() as f64) * 1e-9
    }

    /// Write the session header line. Must be called once, before
    /// any ``write_entry``.
    pub fn write_header(&self, h: &WireLogHeader) -> Result<(), ProtocolError> {
        let mut line = String::from("{\"meta\":{\"version\":1,\"protocol\":");
        line.push_str(&h.version.to_string());
        line.push_str(",\"host\":");
        push_json_string(&mut line, &h.host);
        line.push_str(",\"port\":");
        line.push_str(&h.port.to_string());
        line.push_str(",\"username\":");
        push_json_string(&mut line, &h.username);
        line.push_str("}}");
        let mut w = self.writer.lock().expect("poisoned mutex");
        w.write_all(line.as_bytes())
            .map_err(|e| ProtocolError::DecodeError(format!("header: {}", e)))?;
        w.write_all(b"\n")
            .map_err(|e| ProtocolError::DecodeError(format!("header newline: {}", e)))?;
        w.flush()
            .map_err(|e| ProtocolError::DecodeError(format!("flush: {}", e)))?;
        Ok(())
    }

    /// Write one packet entry as a JSONL line.
    pub fn write_entry(&self, entry: &WireLogEntry) -> Result<(), ProtocolError> {
        let mut line = String::from("{\"ts\":");
        // Round to 6 decimals to match Python's `round(ts, 6)`.
        let ts_rounded = (entry.ts * 1_000_000.0).round() / 1_000_000.0;
        line.push_str(&format_float(ts_rounded));
        line.push_str(",\"dir\":");
        push_json_string(&mut line, entry.direction.label());
        line.push_str(",\"state\":");
        push_json_string(&mut line, entry.state.label());
        line.push_str(",\"id\":");
        line.push_str(&entry.packet_id.to_string());
        line.push_str(",\"raw\":");
        push_json_string(&mut line, &bytes_hex(&entry.raw));
        if let Some(name) = &entry.name {
            line.push_str(",\"name\":");
            push_json_string(&mut line, name);
        }
        line.push('}');
        let mut w = self.writer.lock().expect("poisoned mutex");
        w.write_all(line.as_bytes())
            .map_err(|e| ProtocolError::DecodeError(format!("entry: {}", e)))?;
        w.write_all(b"\n")
            .map_err(|e| ProtocolError::DecodeError(format!("entry newline: {}", e)))?;
        w.flush()
            .map_err(|e| ProtocolError::DecodeError(format!("flush: {}", e)))?;
        Ok(())
    }
}

// --- helpers -------------------------------------------------------------

fn push_json_string(out: &mut String, s: &str) {
    out.push('"');
    for c in s.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                out.push_str(&format!("\\u{:04x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

fn bytes_hex(b: &[u8]) -> String {
    let mut s = String::with_capacity(b.len() * 2);
    for byte in b {
        s.push(HEX[(byte >> 4) as usize]);
        s.push(HEX[(byte & 0x0F) as usize]);
    }
    s
}

const HEX: [char; 16] = [
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f',
];

fn format_float(v: f64) -> String {
    // Match Python's `json.dumps(round(v, 6))` for non-integer floats:
    // Python emits the shortest decimal that round-trips. For our use
    // (seconds since session start, rounded to 6 decimals), we can just
    // format with %g-like trailing-zero stripping.
    if v == 0.0 {
        return "0.0".into();
    }
    let s = format!("{:.6}", v);
    // Drop trailing zeros (but keep at least one digit after the dot).
    let s = s.trim_end_matches('0');
    let s = if s.ends_with('.') {
        format!("{}0", s)
    } else {
        s.to_string()
    };
    s
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Read;

    #[test]
    fn header_then_entry_round_trip() {
        let tmp = std::env::temp_dir().join("wire_log_rust_test.jsonl");
        let _ = std::fs::remove_file(&tmp);
        let log = JsonlFile::create(&tmp).unwrap();
        log.write_header(&WireLogHeader {
            version: 763,
            host: "example.com".into(),
            port: 25565,
            username: "Bot".into(),
        })
        .unwrap();
        log.write_entry(&WireLogEntry {
            ts: 0.123456,
            direction: Direction::Clientbound,
            state: ConnectionState::Login,
            packet_id: 2,
            name: Some("success".into()),
            raw: vec![0xDE, 0xAD, 0xBE, 0xEF],
        })
        .unwrap();
        drop(log);

        let mut s = String::new();
        std::fs::File::open(&tmp)
            .unwrap()
            .read_to_string(&mut s)
            .unwrap();
        let lines: Vec<&str> = s.lines().collect();
        assert_eq!(lines.len(), 2);
        assert!(lines[0].starts_with("{\"meta\":"));
        assert!(lines[1].contains("\"id\":2"));
        assert!(lines[1].contains("\"raw\":\"deadbeef\""));
        assert!(lines[1].contains("\"dir\":\"rx\""));
        assert!(lines[1].contains("\"state\":\"login\""));
        assert!(lines[1].contains("\"name\":\"success\""));
        // ts is rounded to 6 decimals with trailing zeros stripped.
        assert!(lines[1].contains("\"ts\":0.123456"));
    }

    #[test]
    fn format_float_strips_trailing_zeros() {
        assert_eq!(format_float(0.0), "0.0");
        assert_eq!(format_float(1.5), "1.5");
        assert_eq!(format_float(0.123456), "0.123456");
        // 0.100000 → 0.1
        assert_eq!(format_float(0.1), "0.1");
    }
}
