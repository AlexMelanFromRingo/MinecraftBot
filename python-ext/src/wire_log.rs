//! PyO3 `WireLog` class — Python-visible handle around the Rust
//! `wire_log::JsonlFile` sink.
//!
//! Mirrors `python/minecraft_bot/wire_log.py`'s ``WireLog`` API at the
//! level needed for Phase 2 bring-up. Full sink-hierarchy parity
//! (InMemory / LoggerSink / Tee) lands as part of Phase 5 parity work.

use std::path::PathBuf;
use std::sync::Arc;

use minecraft_bot::protocol::v763::states::{ConnectionState, Direction};
use minecraft_bot::wire_log::{JsonlFile, WireLogEntry, WireLogHeader};
use pyo3::prelude::*;
use pyo3::types::PyBytes;

use crate::error_map::IntoPyResult;

/// Python-facing wrapper.
#[pyclass(module = "minecraft_bot_accel", name = "WireLog")]
pub struct PyWireLog {
    inner: Arc<JsonlFile>,
    /// We need the header version to construct the Rust header on
    /// ``start_session``.
    started_header: std::sync::Mutex<bool>,
}

#[pymethods]
impl PyWireLog {
    /// Open ``path`` for write. Mirrors ``WireLog.to_jsonl(path)``.
    #[classmethod]
    fn to_jsonl(_cls: &Bound<'_, pyo3::types::PyType>, path: PathBuf) -> PyResult<Self> {
        let sink = JsonlFile::create(&path).into_py()?;
        Ok(Self {
            inner: Arc::new(sink),
            started_header: std::sync::Mutex::new(false),
        })
    }

    /// Write the session header line. Idempotent.
    #[pyo3(signature = (*, version, host, port, username))]
    fn start_session(&self, version: i32, host: &str, port: u16, username: &str) -> PyResult<()> {
        let mut guard = self.started_header.lock().expect("poisoned mutex");
        if *guard {
            return Ok(());
        }
        let hdr = WireLogHeader {
            version,
            host: host.to_string(),
            port,
            username: username.to_string(),
        };
        self.inner.write_header(&hdr).into_py()?;
        *guard = true;
        Ok(())
    }

    /// Record one packet event.
    #[pyo3(signature = (*, direction, state, packet_id, raw, name = None))]
    fn record(
        &self,
        direction: &str,
        state: &str,
        packet_id: i32,
        raw: &Bound<'_, PyBytes>,
        name: Option<String>,
    ) -> PyResult<()> {
        let dir = parse_direction(direction)?;
        let st = parse_state(state)?;
        let entry = WireLogEntry {
            ts: self.inner.elapsed(),
            direction: dir,
            state: st,
            packet_id,
            name,
            raw: raw.as_bytes().to_vec(),
        };
        self.inner.write_entry(&entry).into_py()?;
        Ok(())
    }

    /// Filesystem path being written to (read-only property).
    #[getter]
    fn path(&self) -> String {
        self.inner.path().to_string_lossy().to_string()
    }

    fn __repr__(&self) -> String {
        format!(
            "WireLog(path={:?})",
            self.inner.path().display().to_string()
        )
    }
}

fn parse_direction(s: &str) -> PyResult<Direction> {
    match s {
        "rx" | "clientbound" => Ok(Direction::Clientbound),
        "tx" | "serverbound" => Ok(Direction::Serverbound),
        other => Err(pyo3::exceptions::PyValueError::new_err(format!(
            "unknown direction label {:?}",
            other
        ))),
    }
}

fn parse_state(s: &str) -> PyResult<ConnectionState> {
    // 001-era Rust ConnectionState has no Configuration variant; the
    // play handshake on protocol 763 also skips it.
    match s {
        "handshaking" => Ok(ConnectionState::Handshaking),
        "status" => Ok(ConnectionState::Status),
        "login" => Ok(ConnectionState::Login),
        "play" => Ok(ConnectionState::Play),
        other => Err(pyo3::exceptions::PyValueError::new_err(format!(
            "unknown connection-state label {:?}",
            other
        ))),
    }
}

/// Register `WireLog` on the parent module.
pub fn register(_py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.add_class::<PyWireLog>()?;
    Ok(())
}
