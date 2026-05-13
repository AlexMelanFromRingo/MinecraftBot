//! Accel async wrappers for Group B movement methods (T029):
//! `look_at`, `jump`, `sneak`, `sprint`, `swing_arm`. Each returns
//! an `awaitable` coroutine via
//! `pyo3_async_runtimes::tokio::future_into_py` so user code does
//! `await bot.look_at(...)` exactly like the Python ref.

use std::sync::Arc;

use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;

use super::PyBot;
use crate::error_map::IntoPyResult;

#[pymethods]
impl PyBot {
    /// `look_at(x, y, z)` — rotate to face world point.
    fn look_at<'py>(
        &self,
        py: Python<'py>,
        x: f64,
        y: f64,
        z: f64,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.look_at(x, y, z).await.into_py()
        })
    }

    /// `jump()` — single-tick jump (best-effort, matches Python).
    fn jump<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.jump().await.into_py()
        })
    }

    /// `sneak(enabled)` — toggle sneak intent (matches Python: no
    /// packet sent, only local intent flag updated).
    fn sneak<'py>(&self, py: Python<'py>, enabled: bool) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.sneak(enabled).await.into_py()
        })
    }

    /// `sprint(enabled)` — toggle sprint intent.
    fn sprint<'py>(&self, py: Python<'py>, enabled: bool) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.sprint(enabled).await.into_py()
        })
    }

    /// `swing_arm(hand=0)` — animate arm swing.
    #[pyo3(signature = (hand = 0))]
    fn swing_arm<'py>(&self, py: Python<'py>, hand: i32) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.swing_arm(hand).await.into_py()
        })
    }
}
