//! ``minecraft_bot_accel.codec.varint`` — PyO3 wrapper.

use pyo3::prelude::*;

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

pub fn register(py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new_bound(py, "varint")?;
    m.add_function(wrap_pyfunction!(read, &m)?)?;
    m.add_function(wrap_pyfunction!(write, &m)?)?;
    m.add_function(wrap_pyfunction!(encoded_size, &m)?)?;
    parent.add_submodule(&m)?;
    Ok(())
}
