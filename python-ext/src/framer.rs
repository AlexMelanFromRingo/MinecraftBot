//! ``minecraft_bot_accel.framer.Framer`` — PyO3 wrapper.

use std::cell::RefCell;

use minecraft_bot::framer::Framer as RustFramer;
use pyo3::prelude::*;
use pyo3::types::PyBytes;

use crate::error_map::IntoPyResult;

/// Python-facing `Framer` mirroring `python/minecraft_bot/framer.py`.
#[pyclass(module = "minecraft_bot_accel.framer", name = "Framer")]
pub struct PyFramer {
    inner: RefCell<RustFramer>,
}

#[pymethods]
impl PyFramer {
    #[new]
    #[pyo3(signature = (*, compression_threshold = -1))]
    fn new(compression_threshold: i32) -> Self {
        let inner = if compression_threshold < 0 {
            RustFramer::new()
        } else {
            RustFramer::with_compression(compression_threshold)
        };
        Self {
            inner: RefCell::new(inner),
        }
    }

    /// Push raw socket bytes into the internal buffer.
    fn feed(&self, data: &Bound<'_, PyBytes>) {
        self.inner.borrow_mut().feed(data.as_bytes());
    }

    /// Currently buffered byte count.
    fn buffered_bytes(&self) -> usize {
        self.inner.borrow().buffered_bytes()
    }

    /// Try to extract one complete packet body.
    ///
    /// Returns ``None`` when more bytes are needed.
    fn try_extract<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyBytes>>> {
        let maybe = self.inner.borrow_mut().try_extract().into_py()?;
        Ok(maybe.map(|v| PyBytes::new_bound(py, &v)))
    }

    /// Encode ``body`` as one outbound frame (applies compression if
    /// configured).
    fn encode<'py>(
        &self,
        py: Python<'py>,
        body: &Bound<'_, PyBytes>,
    ) -> PyResult<Bound<'py, PyBytes>> {
        let out = self.inner.borrow().encode(body.as_bytes()).into_py()?;
        Ok(PyBytes::new_bound(py, &out))
    }

    /// Read-only compression threshold.
    #[getter]
    fn compression_threshold(&self) -> i32 {
        self.inner.borrow().compression_threshold
    }
}

/// Register `framer` submodule with the `Framer` class.
pub fn register(py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new_bound(py, "framer")?;
    m.add_class::<PyFramer>()?;
    parent.add_submodule(&m)?;
    Ok(())
}
