//! Conversion from Rust-side ``minecraft_bot::errors::ProtocolError``
//! to a Python exception drawn from ``crate::errors``.
//!
//! Every variant maps to a specific Python class — no path returns a
//! generic ``RuntimeError`` (FR-014, FR-017).

use minecraft_bot::errors::ProtocolError as RustErr;
use pyo3::PyErr;

use crate::errors as pyerr;

/// Map a Rust ``ProtocolError`` to a Python exception instance.
///
/// The mapping mirrors the inheritance hierarchy in
/// ``python/minecraft_bot/errors.py``: each Rust variant chooses the
/// most specific Python class.
pub fn to_pyerr(err: RustErr) -> PyErr {
    match err {
        RustErr::HandshakeFailed(msg) => pyerr::HandshakeFailed::new_err(msg),
        RustErr::LoginFailed(msg) => pyerr::LoginFailed::new_err(msg),
        RustErr::Disconnected(msg) => pyerr::Disconnected::new_err(msg),
        RustErr::KickedByServer(reason) => pyerr::KickedByServer::new_err(reason),
        RustErr::ConnectionDropped(msg) => pyerr::ConnectionDropped::new_err(msg),
        RustErr::KeepAliveTimeout => {
            pyerr::KeepAliveTimeout::new_err("keep-alive timeout")
        }
        RustErr::PeerReset => pyerr::PeerReset::new_err("peer reset"),
        RustErr::DecodeError(msg) => pyerr::DecodeError::new_err(msg),
        RustErr::UnknownPacketId { state, direction, id } => {
            pyerr::UnknownPacketId::new_err(format!(
                "unknown packet id: state={state} dir={direction} id={id}"
            ))
        }
        RustErr::OversizedVarInt { byte_count } => {
            pyerr::OversizedVarInt::new_err(format!("oversized varint ({byte_count} bytes)"))
        }
        RustErr::IncompleteRead { requested, available } => {
            pyerr::IncompleteRead::new_err(format!(
                "incomplete read: requested {requested}, available {available}"
            ))
        }
        RustErr::MalformedNbt(detail) => {
            pyerr::MalformedNbt::new_err(format!("malformed NBT: {detail}"))
        }
        RustErr::EncodeError(msg) => pyerr::EncodeError::new_err(msg),
        RustErr::ConnectionClosed => pyerr::ConnectionClosed::new_err("connection closed"),
        RustErr::Io(io_err) => {
            // I/O errors map to ConnectionDropped at the framework level;
            // the OS-level detail is preserved in the message.
            pyerr::ConnectionDropped::new_err(format!("io error: {io_err}"))
        }
        // ProtocolError is #[non_exhaustive]; future variants fall
        // back to the base class with their Display message.
        other => pyerr::ProtocolError::new_err(format!("{other}")),
    }
}

/// Trait helper for ergonomic ``?``-based conversion in PyO3 functions
/// that internally call Rust APIs returning ``Result<T, ProtocolError>``.
pub trait IntoPyResult<T> {
    /// Convert a ``Result<T, ProtocolError>`` into a ``PyResult<T>``.
    fn into_py(self) -> pyo3::PyResult<T>;
}

impl<T> IntoPyResult<T> for Result<T, RustErr> {
    fn into_py(self) -> pyo3::PyResult<T> {
        self.map_err(to_pyerr)
    }
}
