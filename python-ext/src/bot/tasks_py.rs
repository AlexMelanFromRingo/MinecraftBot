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
    /// `dig(x, y, z, *, expected_block=None)`.
    #[pyo3(signature = (x, y, z, *, expected_block = None))]
    fn dig<'py>(
        &self,
        py: Python<'py>,
        x: i32,
        y: i32,
        z: i32,
        expected_block: Option<u32>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.dig(x, y, z, expected_block).await.into_py()
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

    /// `follow(eid, *, distance=2.0, timeout=60.0)`.
    #[pyo3(signature = (eid, *, distance = 2.0, timeout = 60.0))]
    fn follow<'py>(
        &self,
        py: Python<'py>,
        eid: i32,
        distance: f64,
        timeout: f64,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let mut bot = inner.lock().await;
            bot.follow(eid, distance, Duration::from_secs_f64(timeout))
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
