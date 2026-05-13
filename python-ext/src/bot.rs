//! PyO3 wrapper for `minecraft_bot::bot::Bot`.
//!
//! 004 split: the `PyBot` `#[pyclass]` itself + 003's 13 wrapper
//! methods stay in this file. New 004 method groups land in the
//! sub-files under `bot/` (combat_py.rs, containers_py.rs,
//! inventory_py.rs, movement_py.rs, state_getters.rs, tasks_py.rs,
//! world_query_py.rs). Each sub-file adds another `#[pymethods]
//! impl PyBot { ... }` block — pyo3 0.22 allows multiple
//! `#[pymethods]` blocks per pyclass.

pub mod combat_py;
pub mod containers_py;
pub mod inventory_py;
pub mod movement_py;
pub mod observation_py;
pub mod state_getters;
pub mod tasks_py;
pub mod world_query_py;

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

    // 004 Q1: `entity_id`, `health`, `food`, `position` are sync
    // `#[getter]` properties in `state_getters.rs`. Old 003 async
    // forms removed — see CHANGELOG entry for v0.3.0.

    /// `walk_to(x, y, z, *, timeout=30.0, max_fall=8, wait_for_slot=False)`.
    /// `max_fall` and `wait_for_slot` accepted for Python sig parity;
    /// path-fall cap is hard-coded inside accel walk_to.
    #[pyo3(signature = (x, y, z, *, timeout = 30.0, max_fall = 8, wait_for_slot = false))]
    fn walk_to<'py>(
        &self,
        py: Python<'py>,
        x: f64,
        y: f64,
        z: f64,
        timeout: f64,
        max_fall: i32,
        wait_for_slot: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        let _ = (max_fall, wait_for_slot);
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.walk_to(x, y, z, timeout).await.into_py()
        })
    }

    /// Drop the currently-held item (Player Action drop_item / drop_stack).
    #[pyo3(signature = (*, full_stack = false))]
    fn drop_held_item<'py>(
        &self,
        py: Python<'py>,
        full_stack: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.drop_held_item(full_stack).await.into_py()
        })
    }

    /// `send_raw(payload: bytes)` — send a pre-encoded serverbound
    /// packet. Caller must include the packet-ID varint at the start
    /// of ``payload``. Pairs with the Python reference's typed
    /// encoders: build a packet object via
    /// `minecraft_bot.protocol.v763.packets.<state>.<dir>.<name>`,
    /// run its `encode()` into a Writer, prepend `varint.write(id)`,
    /// hand the bytes to this method.
    fn send_raw<'py>(
        &self,
        py: Python<'py>,
        payload: &Bound<'_, pyo3::types::PyBytes>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        let owned: Vec<u8> = payload.as_bytes().to_vec();
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.send_raw(&owned).await.into_py()
        })
    }

    /// `on_packet(packet_id: int, callback)` — register a callback
    /// for a clientbound packet id. The callback receives
    /// `(packet_id: int, body: bytes)` after the dispatcher has
    /// applied built-in world / state updates but before any auto
    /// keep-alive handling.
    ///
    /// Multiple callbacks per id are allowed and run in registration
    /// order. To decode the body, route through the Python reference's
    /// typed decoders, for example
    /// `from minecraft_bot.protocol.v763.packets.play.clientbound`
    /// `import chat_message; chat_message.decode(Reader(body))`.
    ///
    /// Callbacks run on the dispatcher task; long work should be
    /// dispatched to a separate asyncio task to avoid blocking.
    fn on_packet<'py>(
        &self,
        py: Python<'py>,
        packet_id: i32,
        callback: Py<PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        // Capture the Python callable. The callback is invoked from
        // the tokio dispatcher task; we need to acquire the GIL each
        // time we call it.
        let cb_py = callback;
        future_into_py(py, async move {
            let bot = inner.lock().await;
            let cb = cb_py;
            bot.on_packet(
                packet_id,
                Box::new(move |id, body| {
                    Python::with_gil(|py| {
                        let bytes = pyo3::types::PyBytes::new_bound(py, body);
                        let _ = cb.call1(py, (id, bytes));
                    });
                }),
            )
            .await;
            Ok::<(), pyo3::PyErr>(())
        })
    }

    /// Drop every registered packet hook.
    fn clear_hooks<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.clear_hooks().await;
            Ok::<(), pyo3::PyErr>(())
        })
    }

    /// **Diagnostic** `walk_to_blind(x, y, z, *, timeout=30.0)` —
    /// slides toward the target at 20 Hz with NO path planning and
    /// NO collision checks. Use for testing the position-send loop
    /// in isolation from the pathfinder.
    #[pyo3(signature = (x, y, z, *, timeout = 30.0))]
    fn walk_to_blind<'py>(
        &self,
        py: Python<'py>,
        x: f64,
        y: f64,
        z: f64,
        timeout: f64,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            bot.walk_to_blind(x, y, z, timeout).await.into_py()
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
