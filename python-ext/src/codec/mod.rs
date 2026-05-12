//! PyO3 wrappers for ``minecraft_bot::codec`` primitives.
//!
//! Exposes Python-visible ``Reader`` and ``Writer`` classes and the
//! per-codec submodules (``varint``, ``varlong``, …). Each submodule
//! mirrors the corresponding ``python/minecraft_bot/codec/*`` module.

use std::cell::RefCell;

use minecraft_bot::codec::{
    BytesReader, BytesWriter, Reader as RustReader, Writer as RustWriter,
};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyType};

use crate::error_map::IntoPyResult;

mod nbt;
mod varint;
mod varlong;

/// Python-facing byte-stream reader. Mirrors
/// ``minecraft_bot.codec.Reader``.
#[pyclass(module = "minecraft_bot_accel.codec", name = "Reader")]
pub struct PyReader {
    data: Vec<u8>,
    pos: RefCell<usize>,
}

#[pymethods]
impl PyReader {
    #[new]
    fn new(data: &Bound<'_, PyAny>) -> PyResult<Self> {
        let buf: Vec<u8> = if let Ok(b) = data.downcast::<PyBytes>() {
            b.as_bytes().to_vec()
        } else {
            // Accept bytearray, memoryview by going through PyBytes::from.
            let py_bytes = PyBytes::new_bound_with(data.py(), 0, |_| Ok(()))?;
            let _ = py_bytes;
            let extracted: Vec<u8> = data.extract().map_err(|_| {
                pyo3::exceptions::PyTypeError::new_err(
                    "Reader expects bytes, bytearray, or memoryview",
                )
            })?;
            extracted
        };
        Ok(Self {
            data: buf,
            pos: RefCell::new(0),
        })
    }

    /// Read ``n`` bytes and advance.
    fn read<'py>(&self, py: Python<'py>, n: i64) -> PyResult<Bound<'py, PyBytes>> {
        if n < 0 {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Reader.read: negative length {n}"
            )));
        }
        let n = n as usize;
        let mut pos = self.pos.borrow_mut();
        if *pos + n > self.data.len() {
            return Err(crate::errors::IncompleteRead::new_err(format!(
                "incomplete read: requested {n}, available {}",
                self.data.len() - *pos
            )));
        }
        let slice = &self.data[*pos..*pos + n];
        *pos += n;
        Ok(PyBytes::new_bound(py, slice))
    }

    /// Peek up to ``n`` bytes without advancing.
    fn peek<'py>(&self, py: Python<'py>, n: i64) -> PyResult<Bound<'py, PyBytes>> {
        if n < 0 {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Reader.peek: negative length {n}"
            )));
        }
        let n = n as usize;
        let pos = *self.pos.borrow();
        let end = (pos + n).min(self.data.len());
        Ok(PyBytes::new_bound(py, &self.data[pos..end]))
    }

    /// Bytes still available.
    fn remaining(&self) -> usize {
        self.data.len().saturating_sub(*self.pos.borrow())
    }

    /// Current absolute byte position.
    fn position(&self) -> usize {
        *self.pos.borrow()
    }

    fn __len__(&self) -> usize {
        self.data.len()
    }

    fn __repr__(&self) -> String {
        format!("Reader(pos={}, len={})", self.position(), self.data.len())
    }
}

impl PyReader {
    /// Borrow the internal buffer + position to construct a Rust
    /// ``BytesReader``. Advances the stored position to match the
    /// reader's after the callback runs.
    pub(crate) fn with_rust_reader<F, R>(&self, f: F) -> PyResult<R>
    where
        F: FnOnce(&mut BytesReader<'_>) -> Result<R, minecraft_bot::errors::ProtocolError>,
    {
        let pos = *self.pos.borrow();
        let slice = &self.data[pos..];
        let mut br = BytesReader::new(slice);
        let result = f(&mut br).into_py()?;
        let consumed = br.position();
        *self.pos.borrow_mut() = pos + consumed;
        Ok(result)
    }
}

/// Python-facing byte-stream writer. Mirrors
/// ``minecraft_bot.codec.Writer``.
#[pyclass(module = "minecraft_bot_accel.codec", name = "Writer")]
pub struct PyWriter {
    buf: RefCell<BytesWriter>,
}

#[pymethods]
impl PyWriter {
    #[new]
    fn new() -> Self {
        Self {
            buf: RefCell::new(BytesWriter::new()),
        }
    }

    /// Append raw bytes.
    fn write(&self, b: &Bound<'_, PyBytes>) -> PyResult<()> {
        self.buf
            .borrow_mut()
            .write_all(b.as_bytes())
            .into_py()
    }

    /// Final byte string.
    fn bytes<'py>(&self, py: Python<'py>) -> Bound<'py, PyBytes> {
        PyBytes::new_bound(py, self.buf.borrow().as_slice())
    }

    fn __len__(&self) -> usize {
        self.buf.borrow().len()
    }

    fn __repr__(&self) -> String {
        format!("Writer(len={})", self.__len__())
    }
}

impl PyWriter {
    /// Borrow the inner ``BytesWriter`` mutably for codec calls.
    pub(crate) fn with_rust_writer<F, R>(&self, f: F) -> PyResult<R>
    where
        F: FnOnce(&mut BytesWriter) -> Result<R, minecraft_bot::errors::ProtocolError>,
    {
        let mut w = self.buf.borrow_mut();
        f(&mut *w).into_py()
    }
}

/// Register `codec` submodule with `Reader`, `Writer`, and the codec
/// subsubmodules.
pub fn register(py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new_bound(py, "codec")?;
    m.add_class::<PyReader>()?;
    m.add_class::<PyWriter>()?;

    // Sub-submodules.
    varint::register(py, &m)?;
    varlong::register(py, &m)?;
    nbt::register(py, &m)?;

    parent.add_submodule(&m)?;
    Ok(())
}
