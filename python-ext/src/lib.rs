//! `minecraft_bot_accel` — PyO3 façade over the `minecraft_bot` Rust crate.
//!
//! This module is the root of the native package; each submodule
//! mirrors the corresponding Python module from `minecraft_bot`.

use pyo3::prelude::*;

mod behaviour_py;
mod bot;
mod codec;
mod effects_py;
mod entities;
mod error_map;
mod errors;
mod foods_py;
mod framer;
mod observation;
mod pathfinding;
mod physics;
mod runtime;
mod slots;
mod version;
mod wire_log;
mod world;

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
    world::register(py, &m)?;
    pathfinding::register(py, &m)?;
    physics::register(py, &m)?;
    observation::register(py, &m)?;
    entities::register(py, &m)?;
    effects_py::register(py, &m)?;
    slots::register(py, &m)?;
    bot::register(py, &m)?;
    // 004 additions (stubs until filled in by Group I / T017).
    behaviour_py::register(py, &m)?;
    foods_py::register(py, &m)?;

    Ok(())
}
