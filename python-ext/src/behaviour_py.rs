//! Accel wrappers for the Rust behaviour-tree (Selector, Sequencer,
//! Inverter, Repeater, standard leaves, BehaviourRunner). Filled in
//! by 004 Group I (T075). For now this is a no-op registrar so
//! `import minecraft_bot_accel` works during Phase 1.

use pyo3::prelude::*;

/// Stub registrar. Will be filled in to expose the behaviour-tree
/// types as `#[pyclass]` in T075.
pub fn register(_py: Python<'_>, _m: &Bound<'_, PyModule>) -> PyResult<()> {
    Ok(())
}
