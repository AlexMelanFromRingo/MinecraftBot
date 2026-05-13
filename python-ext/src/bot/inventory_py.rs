//! Accel wrappers for Group F inventory methods (T055). Read-only
//! methods are sync to match Python's `@property` shape; mutators
//! are async to match Python's `await`.

use std::sync::Arc;

use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;

use super::PyBot;
use crate::error_map::IntoPyResult;
use crate::runtime;

/// Python view of an item slot (matches `minecraft_bot.ItemSlot`).
#[pyclass(module = "minecraft_bot_accel", name = "ItemSlot", frozen)]
#[derive(Clone)]
pub struct PyItemSlot {
    #[pyo3(get)]
    pub item_id: u32,
    #[pyo3(get)]
    pub count: u8,
    #[pyo3(get)]
    pub name: String,
}

impl PyItemSlot {
    fn from_inner(s: minecraft_bot::inventory::ItemSlot) -> Self {
        let name = s.name();
        Self {
            item_id: s.item_id,
            count: s.count,
            name,
        }
    }
}

#[pymethods]
impl PyItemSlot {
    fn __repr__(&self) -> String {
        format!("ItemSlot(name={:?}, count={})", self.name, self.count)
    }
}

#[pymethods]
impl PyBot {
    /// Sync property: currently-held item.
    #[getter]
    fn held_item(&self, py: Python<'_>) -> Option<PyItemSlot> {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.held_item().await.map(PyItemSlot::from_inner)
            })
        })
    }

    /// `find_item(name) -> Optional[int]`.
    fn find_item(&self, py: Python<'_>, name: String) -> Option<usize> {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.find_item(&name).await
            })
        })
    }

    /// `count_item(name) -> int`.
    fn count_item(&self, py: Python<'_>, name: String) -> u32 {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.count_item(&name).await
            })
        })
    }

    /// `iter_accessible_slots() -> list[(int, Optional[ItemSlot])]`.
    fn iter_accessible_slots(&self, py: Python<'_>) -> Vec<(usize, Option<PyItemSlot>)> {
        let inner = self.inner.clone();
        py.allow_threads(|| {
            runtime::tokio().block_on(async move {
                let bot = inner.lock().await;
                bot.iter_accessible_slots()
                    .await
                    .into_iter()
                    .map(|(i, s)| (i, s.map(PyItemSlot::from_inner)))
                    .collect()
            })
        })
    }

    /// `select_slot(hotbar_index)`.
    fn select_slot<'py>(
        &self,
        py: Python<'py>,
        hotbar_index: u8,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.select_slot(hotbar_index).await.into_py()
        })
    }

    /// `drop_item(*, drop_stack=False)`.
    #[pyo3(signature = (*, drop_stack = false))]
    fn drop_item<'py>(
        &self,
        py: Python<'py>,
        drop_stack: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.drop_item(drop_stack).await.into_py()
        })
    }

    /// `click_slot(slot_index, *, mode='left', button=0, window_id=None,
    /// wait_for_slot=False)`. `wait_for_slot` is accepted for Python
    /// signature parity but treated as a no-op on accel (the inner
    /// inventory mutex already serialises clicks).
    #[pyo3(signature = (slot_index, *, mode = String::from("left"), button = 0, window_id = None, wait_for_slot = false))]
    fn click_slot<'py>(
        &self,
        py: Python<'py>,
        slot_index: i16,
        mode: String,
        button: i8,
        window_id: Option<u8>,
        wait_for_slot: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        let _ = wait_for_slot;
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.click_slot(slot_index, &mode, button, window_id)
                .await
                .into_py()
        })
    }

    /// `move_item(src_slot, dst_slot, *, window_id=None)`.
    #[pyo3(signature = (src_slot, dst_slot, *, window_id = None))]
    fn move_item<'py>(
        &self,
        py: Python<'py>,
        src_slot: i16,
        dst_slot: i16,
        window_id: Option<u8>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.move_item(src_slot, dst_slot, window_id).await.into_py()
        })
    }

    /// `quick_move(slot_index, *, window_id=None)`.
    #[pyo3(signature = (slot_index, *, window_id = None))]
    fn quick_move<'py>(
        &self,
        py: Python<'py>,
        slot_index: i16,
        window_id: Option<u8>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.quick_move(slot_index, window_id).await.into_py()
        })
    }

    /// `equip_armor(armor_slot, src_slot)`.
    fn equip_armor<'py>(
        &self,
        py: Python<'py>,
        armor_slot: String,
        src_slot: i16,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.equip_armor(&armor_slot, src_slot).await.into_py()
        })
    }

    /// `unequip_armor(armor_slot, dst_slot)`.
    fn unequip_armor<'py>(
        &self,
        py: Python<'py>,
        armor_slot: String,
        dst_slot: i16,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.unequip_armor(&armor_slot, dst_slot).await.into_py()
        })
    }

    /// `swap_to_offhand(src_slot)`.
    fn swap_to_offhand<'py>(
        &self,
        py: Python<'py>,
        src_slot: i16,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.swap_to_offhand(src_slot).await.into_py()
        })
    }
}

/// Register `ItemSlot` pyclass on the top-level module.
pub fn register(_py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.add_class::<PyItemSlot>()?;
    Ok(())
}
