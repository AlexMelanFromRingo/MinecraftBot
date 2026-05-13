//! Accel async wrappers for Group G container methods (T062).

use std::sync::Arc;
use std::time::Duration;

use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;

use super::PyBot;
use crate::error_map::IntoPyResult;

#[pymethods]
impl PyBot {
    /// `open_block_container(x, y, z, *, timeout=5.0, wait_for_slot=False,
    /// face=None, cursor=None) -> int`. `wait_for_slot`, `face`, `cursor`
    /// accepted for Python sig parity but ignored on accel (the inner
    /// container_slot lock + look_at handle face selection automatically).
    #[pyo3(signature = (
        x, y, z, *,
        timeout = 5.0,
        wait_for_slot = false,
        face = None,
        cursor = None,
    ))]
    fn open_block_container<'py>(
        &self,
        py: Python<'py>,
        x: i32,
        y: i32,
        z: i32,
        timeout: f64,
        wait_for_slot: bool,
        face: Option<i32>,
        cursor: Option<(f64, f64, f64)>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let _ = (wait_for_slot, face, cursor);
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.open_block_container(x, y, z, Duration::from_secs_f64(timeout))
                .await
                .into_py()
        })
    }

    /// `open_chest(x, y, z, *, timeout=5.0)`.
    #[pyo3(signature = (x, y, z, *, timeout = 5.0))]
    fn open_chest<'py>(
        &self,
        py: Python<'py>,
        x: i32,
        y: i32,
        z: i32,
        timeout: f64,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.open_chest(x, y, z, Duration::from_secs_f64(timeout))
                .await
                .into_py()
        })
    }

    /// `open_furnace(x, y, z, *, timeout=5.0)`.
    #[pyo3(signature = (x, y, z, *, timeout = 5.0))]
    fn open_furnace<'py>(
        &self,
        py: Python<'py>,
        x: i32,
        y: i32,
        z: i32,
        timeout: f64,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.open_furnace(x, y, z, Duration::from_secs_f64(timeout))
                .await
                .into_py()
        })
    }

    /// `open_crafting_table(x, y, z, *, timeout=5.0)`.
    #[pyo3(signature = (x, y, z, *, timeout = 5.0))]
    fn open_crafting_table<'py>(
        &self,
        py: Python<'py>,
        x: i32,
        y: i32,
        z: i32,
        timeout: f64,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.open_crafting_table(x, y, z, Duration::from_secs_f64(timeout))
                .await
                .into_py()
        })
    }

    /// `close_container()`.
    fn close_container<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.close_container().await.into_py()
        })
    }

    /// `craft(recipe, x, y, z, *, repeat=1, timeout=8.0) -> int`.
    #[pyo3(signature = (recipe, x, y, z, *, repeat = 1, timeout = 8.0))]
    fn craft<'py>(
        &self,
        py: Python<'py>,
        recipe: Vec<Option<String>>,
        x: i32,
        y: i32,
        z: i32,
        repeat: u32,
        timeout: f64,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            if recipe.len() != 9 {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "recipe must be a 9-element list",
                ));
            }
            let mut grid: [Option<String>; 9] = Default::default();
            for (i, v) in recipe.into_iter().enumerate() {
                grid[i] = v;
            }
            let bot = inner.lock().await;
            bot.craft(grid, x, y, z, repeat, Duration::from_secs_f64(timeout))
                .await
                .into_py()
        })
    }
}
