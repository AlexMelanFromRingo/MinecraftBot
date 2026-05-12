//! ``minecraft_bot_accel.codec.varint`` — PyO3 wrapper.

use minecraft_bot::codec::{BytesReader, BytesWriter};
use minecraft_bot::errors::ProtocolError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyList};

use super::{PyReader, PyWriter};

/// Read one VarInt from ``reader``; advance the reader by the number
/// of bytes consumed.
#[pyfunction]
fn read(reader: &PyReader) -> PyResult<i32> {
    reader.with_rust_reader(|r| minecraft_bot::codec::varint::read(r))
}

/// Write ``value`` as a VarInt into ``writer``.
#[pyfunction]
fn write(value: i32, writer: &PyWriter) -> PyResult<()> {
    writer.with_rust_writer(|w| minecraft_bot::codec::varint::write(value, w))
}

/// Number of bytes ``value`` will occupy on the wire.
#[pyfunction]
fn encoded_size(value: i32) -> usize {
    minecraft_bot::codec::varint::encoded_size(value)
}

/// **Batched read** — `read_many(buf, n) -> list[int]`. Decode `n`
/// consecutive VarInts from `buf` in one FFI call. Amortises the
/// per-call PyO3 boundary cost (≈ 2 µs/op) across the whole batch,
/// so for `n=1000` the per-value cost falls from ~2 µs to ~30 ns.
#[pyfunction]
fn read_many<'py>(
    py: Python<'py>,
    buf: &Bound<'_, PyBytes>,
    n: usize,
) -> PyResult<Bound<'py, PyList>> {
    let owned: Vec<u8> = buf.as_bytes().to_vec();
    let decoded: Result<Vec<i32>, ProtocolError> = py.allow_threads(move || {
        let mut r = BytesReader::new(&owned);
        let mut out = Vec::with_capacity(n);
        for _ in 0..n {
            out.push(minecraft_bot::codec::varint::read(&mut r)?);
        }
        Ok(out)
    });
    let values = decoded.map_err(crate::error_map::to_pyerr)?;
    let lst = PyList::empty_bound(py);
    for v in values {
        lst.append(v)?;
    }
    Ok(lst)
}

/// **Batched write** — `write_many(values) -> bytes`. Encode every
/// VarInt in `values` into a single bytes buffer in one FFI call.
#[pyfunction]
fn write_many<'py>(py: Python<'py>, values: Vec<i32>) -> PyResult<Bound<'py, PyBytes>> {
    let encoded: Result<Vec<u8>, ProtocolError> = py.allow_threads(move || {
        let mut w = BytesWriter::new();
        for v in &values {
            minecraft_bot::codec::varint::write(*v, &mut w)?;
        }
        Ok(w.into_bytes())
    });
    let bytes = encoded.map_err(crate::error_map::to_pyerr)?;
    Ok(PyBytes::new_bound(py, &bytes))
}

pub fn register(py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new_bound(py, "varint")?;
    m.add_function(wrap_pyfunction!(read, &m)?)?;
    m.add_function(wrap_pyfunction!(write, &m)?)?;
    m.add_function(wrap_pyfunction!(encoded_size, &m)?)?;
    m.add_function(wrap_pyfunction!(read_many, &m)?)?;
    m.add_function(wrap_pyfunction!(write_many, &m)?)?;
    parent.add_submodule(&m)?;
    Ok(())
}
