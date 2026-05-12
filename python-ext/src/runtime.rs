//! Process-wide tokio runtime for `minecraft_bot_accel`.
//!
//! `pyo3-async-runtimes` needs a single tokio runtime to host all Rust
//! futures that get bridged to Python awaitables. We initialise that
//! runtime exactly once via a ``OnceLock`` and hand the same handle to
//! every ``future_into_py`` call.
//!
//! Constitution VII (determinism): only one runtime per process; no
//! per-Bot runtimes that could race or duplicate timers.

use std::sync::OnceLock;
use tokio::runtime::{Builder, Runtime};

static TOKIO: OnceLock<Runtime> = OnceLock::new();

/// Build the runtime on first call; return a reference to it on every
/// call after.
///
/// Uses the multi-thread scheduler with worker_threads at the default
/// (cpu count). I/O and time drivers are both enabled — Connection
/// needs both.
pub fn tokio() -> &'static Runtime {
    TOKIO.get_or_init(|| {
        Builder::new_multi_thread()
            .enable_all()
            .thread_name("mb-accel-tokio")
            .build()
            .expect("failed to build tokio runtime for minecraft_bot_accel")
    })
}

/// Register the runtime with `pyo3-async-runtimes` so
/// `future_into_py` and `into_future` use the same handle.
///
/// Called once from the `#[pymodule]` init in `lib.rs`.
pub fn init_once() {
    // Force-build the runtime, then hand its Handle to the bridge layer.
    let rt = tokio();
    pyo3_async_runtimes::tokio::init_with_runtime(rt)
        .expect("pyo3_async_runtimes::tokio::init_with_runtime() failed");
}
