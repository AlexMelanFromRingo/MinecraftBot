//! Accel async wrappers for Group H high-level task methods (T069):
//! dig, eat, follow, say, chat.

use std::sync::Arc;
use std::time::Duration;

use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;

use super::PyBot;
use crate::error_map::IntoPyResult;

#[pymethods]
impl PyBot {
    /// `dig(x, y, z, *, tool=None, timeout_multiplier=2.0,
    /// wait_for_slot=False, expected_block=None)`. `tool`,
    /// `timeout_multiplier`, `wait_for_slot` are accepted for
    /// Python sig parity; accel uses the hardness table + a
    /// safety clamp internally (v0.3.1).
    #[pyo3(signature = (
        x, y, z, *,
        tool = None,
        timeout_multiplier = 2.0,
        wait_for_slot = false,
    ))]
    fn dig<'py>(
        &self,
        py: Python<'py>,
        x: i32,
        y: i32,
        z: i32,
        tool: Option<String>,
        timeout_multiplier: f64,
        wait_for_slot: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        let _ = (tool, timeout_multiplier, wait_for_slot);
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.dig(x, y, z, None).await.into_py()
        })
    }

    /// `eat(*, timeout=3.0)`.
    #[pyo3(signature = (*, timeout = 3.0))]
    fn eat<'py>(&self, py: Python<'py>, timeout: f64) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.eat(Duration::from_secs_f64(timeout)).await.into_py()
        })
    }

    /// `follow(eid, *, distance=3.0, timeout=None, wait_for_slot=False,
    /// re_path_radius=2.0)`. `wait_for_slot` and `re_path_radius` are
    /// accepted for Python sig parity (`re_path_radius` is hard-coded
    /// to 2.0 in the Rust impl).
    #[pyo3(signature = (
        eid, *,
        distance = 3.0,
        timeout = None,
        wait_for_slot = false,
        re_path_radius = 2.0,
    ))]
    fn follow<'py>(
        &self,
        py: Python<'py>,
        eid: i32,
        distance: f64,
        timeout: Option<f64>,
        wait_for_slot: bool,
        re_path_radius: f64,
    ) -> PyResult<Bound<'py, PyAny>> {
        let _ = (wait_for_slot, re_path_radius);
        let inner = Arc::clone(&self.inner);
        let timeout_secs = timeout.unwrap_or(60.0);
        future_into_py(py, async move {
            let mut bot = inner.lock().await;
            bot.follow(eid, distance, Duration::from_secs_f64(timeout_secs))
                .await
                .into_py()
        })
    }

    /// `say(message)`.
    fn say<'py>(&self, py: Python<'py>, message: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.say(&message).await.into_py()
        })
    }

    /// `chat(message)` — alias for `say`.
    fn chat<'py>(&self, py: Python<'py>, message: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.chat(&message).await.into_py()
        })
    }
}
