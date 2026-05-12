//! PyO3 wrap: PyItemStack mirroring `python/minecraft_bot.inventory.item.ItemSlot`.
//!
//! Wire-level SlotData from `minecraft_bot::codec::slot::SlotData` plus
//! item-id ↔ name lookups (deferred — item_table not yet wired).

use minecraft_bot::codec::slot::SlotData;
use pyo3::prelude::*;
use pyo3::types::PyBytes;

#[pyclass(module = "minecraft_bot_accel", name = "ItemStack")]
#[derive(Clone)]
pub struct PyItemStack {
    item_id: i32,
    count: i8,
    nbt_raw: Vec<u8>,
}

#[pymethods]
impl PyItemStack {
    #[new]
    #[pyo3(signature = (item_id, count, *, nbt = None))]
    fn new(item_id: i32, count: i8, nbt: Option<Vec<u8>>) -> Self {
        Self {
            item_id,
            count,
            nbt_raw: nbt.unwrap_or_default(),
        }
    }

    #[getter] fn item_id(&self) -> i32 { self.item_id }
    #[getter] fn count(&self) -> i8 { self.count }

    /// Raw NBT bytes (opaque; parse separately if needed).
    #[getter]
    fn nbt<'py>(&self, py: Python<'py>) -> Bound<'py, PyBytes> {
        PyBytes::new_bound(py, &self.nbt_raw)
    }

    fn __eq__(&self, other: &Self) -> bool {
        self.item_id == other.item_id
            && self.count == other.count
            && self.nbt_raw == other.nbt_raw
    }

    fn __repr__(&self) -> String {
        format!(
            "ItemStack(item_id={}, count={}, nbt={} bytes)",
            self.item_id, self.count, self.nbt_raw.len(),
        )
    }
}

impl PyItemStack {
    /// Build a PyItemStack from a wire-level SlotData.
    pub fn from_slot_data(s: &SlotData) -> Self {
        Self {
            item_id: s.item_id,
            count: s.count,
            nbt_raw: Vec::new(), // NBT round-trip deferred
        }
    }
}

pub fn register(_py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.add_class::<PyItemStack>()?;
    Ok(())
}
