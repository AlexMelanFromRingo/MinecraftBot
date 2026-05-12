//! ``minecraft_bot_accel.codec.varlong`` — PyO3 wrapper.

use pyo3::prelude::*;

use super::{PyReader, PyWriter};

#[pyfunction]
fn read(reader: &PyReader) -> PyResult<i64> {
    reader.with_rust_reader(|r| minecraft_bot::codec::varlong::read(r))
}

#[pyfunction]
fn write(value: i64, writer: &PyWriter) -> PyResult<()> {
    writer.with_rust_writer(|w| minecraft_bot::codec::varlong::write(value, w))
}

pub fn register(py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new_bound(py, "varlong")?;
    m.add_function(wrap_pyfunction!(read, &m)?)?;
    m.add_function(wrap_pyfunction!(write, &m)?)?;
    parent.add_submodule(&m)?;
    Ok(())
}
