//! PyO3 wrapper for `minecraft_bot::bot::Bot`.

use std::sync::Arc;

use minecraft_bot::bot::Bot as RustBot;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use tokio::sync::Mutex;

use crate::error_map::IntoPyResult;
use crate::world::PyWorld;

/// Python-facing Bot handle.
#[pyclass(module = "minecraft_bot_accel", name = "Bot")]
pub struct PyBot {
    inner: Arc<Mutex<RustBot>>,
    /// Cached PyWorld view (created on first `world` access).
    world_handle: Arc<Mutex<Option<Py<PyWorld>>>>,
}

#[pymethods]
impl PyBot {
    /// `Bot.offline(host, port, username) -> Bot`
    #[classmethod]
    fn offline(
        _cls: &Bound<'_, pyo3::types::PyType>,
        host: String,
        port: u16,
        username: String,
    ) -> Self {
        Self {
            inner: Arc::new(Mutex::new(RustBot::offline(host, port, username))),
            world_handle: Arc::new(Mutex::new(None)),
        }
    }

    /// Connect (login → play) and start the packet dispatcher.
    fn connect<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let mut bot = inner.lock().await;
            bot.connect().await.into_py()
        })
    }

    /// Graceful disconnect.
    fn disconnect<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let mut bot = inner.lock().await;
            bot.disconnect().await.into_py()
        })
    }

    /// Bot's server-assigned entity id (from Login packet). Async to
    /// match `Connection::entity_id` semantics.
    fn entity_id<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            Ok(bot.entity_id().await)
        })
    }

    /// Last-known health.
    fn health<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            Ok(bot.health().await)
        })
    }

    /// Last-known food.
    fn food<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            Ok(bot.food().await)
        })
    }

    /// Last-known position `(x, y, z, yaw, pitch)`, or `None` if
    /// the server has not yet sent a `synchronize_player_position`
    /// packet.
    fn position<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            Ok(bot.position().await)
        })
    }

    /// Number of loaded chunks (synchronous; reads via RwLock).
    fn loaded_chunk_count<'py>(&self, py: Python<'py>) -> PyResult<usize> {
        let inner = self.inner.clone();
        py.allow_threads(move || {
            // Synchronous lock is fine: we don't await inside.
            let bot = inner.blocking_lock();
            Ok(bot.world.loaded_chunk_count())
        })
    }

    /// `World` view of the bot's cache (shared Arc).
    #[getter]
    fn world<'py>(&self, py: Python<'py>) -> PyResult<Py<PyWorld>> {
        // Lazily build a PyWorld wrapping the same Arc<World>.
        let inner = self.inner.clone();
        let world_arc = py.allow_threads(move || {
            let bot = inner.blocking_lock();
            Arc::clone(&bot.world)
        });
        let pyworld = PyWorld::from_arc(world_arc);
        Py::new(py, pyworld)
    }

    fn __repr__(&self) -> String {
        "Bot(...)".to_string()
    }
}

/// Register the `Bot` class on the parent module.
pub fn register(_py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.add_class::<PyBot>()?;
    Ok(())
}
