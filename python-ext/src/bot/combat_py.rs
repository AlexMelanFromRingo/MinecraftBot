//! Accel async wrappers for Group C combat methods (T033):
//! `attack`, `interact_entity`, `use_item`.

use std::sync::Arc;

use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;

use super::PyBot;
use crate::error_map::IntoPyResult;

#[pymethods]
impl PyBot {
    /// `attack(eid)` — UseEntity(attack) + arm swing.
    fn attack<'py>(&self, py: Python<'py>, eid: i32) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.attack(eid).await.into_py()
        })
    }

    /// `interact_entity(eid, *, hand=0)` — UseEntity(interact).
    #[pyo3(signature = (eid, *, hand = 0))]
    fn interact_entity<'py>(
        &self,
        py: Python<'py>,
        eid: i32,
        hand: i32,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.interact_entity(eid, hand).await.into_py()
        })
    }

    /// `use_item(hand=0)` — right-click currently held item.
    #[pyo3(signature = (hand = 0))]
    fn use_item<'py>(&self, py: Python<'py>, hand: i32) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.use_item(hand).await.into_py()
        })
    }
}
