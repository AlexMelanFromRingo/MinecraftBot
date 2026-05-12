//! `minecraft_bot_accel` — PyO3 façade over the `minecraft_bot` Rust crate.
//!
//! This module is the root of the native package; each submodule
//! mirrors the corresponding Python module from `minecraft_bot`.

use pyo3::prelude::*;

mod errors;
mod error_map;
mod runtime;
mod version;
mod wire_log;
mod framer;
mod codec;

#[pymodule]
fn minecraft_bot_accel(py: Python<'_>, m: Bound<'_, PyModule>) -> PyResult<()> {
    // Initialise the process-wide tokio runtime and cross-register it
    // with pyo3-async-runtimes. Idempotent — does nothing on second
    // import.
    runtime::init_once();

    // Module-level identity attributes (__version__, python_compat,
    // implementation).
    version::register(&m)?;

    // Submodules.
    errors::register(py, &m)?;
    wire_log::register(py, &m)?;
    framer::register(py, &m)?;
    codec::register(py, &m)?;

    Ok(())
}
