//! Accel wrapper exposing the food table to Python. Filled in by
//! 004 T017. For now this is a no-op registrar.

use pyo3::prelude::*;

/// Stub registrar. Will be filled in to expose
/// `minecraft_bot_accel.foods.lookup(item_id) -> (hunger, saturation)`
/// in T017.
pub fn register(_py: Python<'_>, _m: &Bound<'_, PyModule>) -> PyResult<()> {
    Ok(())
}
