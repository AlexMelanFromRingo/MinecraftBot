//! PyO3 façade for `minecraft_bot::world`.
//!
//! Exposes `World`, `Chunk` (read-only view), and the
//! `decode_chunk(payload, cx, cz, min_y, section_count)` entry point.
//! Block-state classification predicates (`is_solid`, `is_water`, …)
//! mirror the Python `world.block_table` module's free functions.

use std::sync::Arc;

use minecraft_bot::world as rw;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyList, PyTuple};

use crate::error_map::IntoPyResult;

/// Native-side `World` handle (shared via Arc so multiple Python
/// references see the same cache).
#[pyclass(module = "minecraft_bot_accel.world", name = "World")]
pub struct PyWorld {
    inner: Arc<rw::World>,
}

#[pymethods]
impl PyWorld {
    #[new]
    #[pyo3(signature = (*, dimension = "minecraft:overworld", min_y = -64, section_count = 24))]
    fn new(dimension: &str, min_y: i32, section_count: i32) -> Self {
        Self {
            inner: Arc::new(rw::World::with_dimension(dimension, min_y, section_count)),
        }
    }

    /// Block-state ID at `(x, y, z)`, or `0` if unloaded / OOR.
    fn get_block_id(&self, x: i32, y: i32, z: i32) -> i32 {
        self.inner.get_block_id(x, y, z)
    }

    /// Block name at `(x, y, z)`, or `None`.
    fn get_block_name(&self, x: i32, y: i32, z: i32) -> Option<&'static str> {
        self.inner.get_block_name(x, y, z)
    }

    /// Number of loaded chunks.
    fn loaded_chunk_count(&self) -> usize {
        self.inner.loaded_chunk_count()
    }

    /// Predicate: solid block.
    fn is_solid(&self, x: i32, y: i32, z: i32) -> bool {
        self.inner.is_solid(x, y, z)
    }

    /// Predicate: water cell.
    fn is_water(&self, x: i32, y: i32, z: i32) -> bool {
        self.inner.is_water(x, y, z)
    }

    /// Predicate: navigable obstacle.
    fn is_navigable_obstacle(&self, x: i32, y: i32, z: i32) -> bool {
        self.inner.is_navigable_obstacle(x, y, z)
    }

    /// Apply a `block_change` (single-block update).
    fn apply_block_change(&self, x: i32, y: i32, z: i32, state_id: i32) {
        self.inner.set_block(x, y, z, state_id);
    }

    /// Apply a `map_chunk` payload, decoding it into a `Chunk` and
    /// storing it in the cache. Returns the chunk's `(cx, cz)` for
    /// the caller's convenience.
    fn apply_map_chunk<'py>(
        &self,
        py: Python<'py>,
        payload: &Bound<'_, PyBytes>,
        cx: i32,
        cz: i32,
    ) -> PyResult<Bound<'py, PyTuple>> {
        let min_y = self.inner.min_y();
        let sc = self.inner.section_count();
        // Copy bytes out of the Python buffer so the heavy decode can
        // run without the GIL.
        let bytes: Vec<u8> = payload.as_bytes().to_vec();
        let chunk = py
            .allow_threads(move || rw::decode_chunk(&bytes, cx, cz, min_y, sc))
            .into_py()?;
        let coords = (chunk.cx, chunk.cz);
        self.inner.insert_chunk(chunk);
        Ok(PyTuple::new_bound(py, [coords.0, coords.1]))
    }

    /// Drop a chunk (server-driven unload).
    fn apply_unload_chunk(&self, cx: i32, cz: i32) {
        self.inner.unload_chunk(cx, cz);
    }

    /// Find blocks matching `name` within Chebyshev radius `radius`.
    /// Returns list of (x, y, z) tuples sorted by distance.
    #[pyo3(signature = (name, origin, *, radius = 32, limit = 16))]
    fn find_blocks_nearby<'py>(
        &self,
        py: Python<'py>,
        name: &str,
        origin: (f64, f64, f64),
        radius: i32,
        limit: usize,
    ) -> PyResult<Bound<'py, PyList>> {
        let owned_name = name.to_string();
        let world = self.arc();
        let results =
            py.allow_threads(move || world.find_blocks_nearby(&owned_name, origin, radius, limit));
        let list = PyList::empty_bound(py);
        for (x, y, z) in results {
            list.append(PyTuple::new_bound(py, [x, y, z]))?;
        }
        Ok(list)
    }

    /// Dimension identifier.
    #[getter]
    fn dimension(&self) -> String {
        self.inner.dimension()
    }

    /// Floor of the loaded vertical range.
    #[getter]
    fn min_y(&self) -> i32 {
        self.inner.min_y()
    }

    /// Section count.
    #[getter]
    fn section_count(&self) -> i32 {
        self.inner.section_count()
    }

    fn __repr__(&self) -> String {
        format!(
            "World(dimension={:?}, loaded={}, min_y={}, section_count={})",
            self.inner.dimension(),
            self.inner.loaded_chunk_count(),
            self.inner.min_y(),
            self.inner.section_count(),
        )
    }
}

impl PyWorld {
    /// Borrow the inner `Arc<World>` for cross-module access (e.g. by
    /// the `Bot` facade or pathfinder wrapper).
    pub fn arc(&self) -> Arc<rw::World> {
        Arc::clone(&self.inner)
    }

    /// Construct a `PyWorld` view over an existing shared `World`.
    pub fn from_arc(world: Arc<rw::World>) -> Self {
        Self { inner: world }
    }
}

/// Free function: classification predicates from `block_table`.
#[pyfunction]
fn block_is_solid(state_id: i32) -> bool {
    rw::block_table::is_solid(state_id)
}

/// Free function: water classification.
#[pyfunction]
fn block_is_water(state_id: i32) -> bool {
    rw::block_table::is_water(state_id)
}

/// Free function: block name for a state id.
#[pyfunction]
fn block_name(state_id: i32) -> Option<&'static str> {
    rw::block_table::get_name(state_id)
}

/// Standalone decode (not wired into a World). Returns a tuple
/// `(section_count, block_entities_count, first_section_first_cell)`
/// for parity verification.
#[pyfunction]
fn decode_chunk_summary(
    py: Python<'_>,
    payload: &Bound<'_, PyBytes>,
    cx: i32,
    cz: i32,
    min_y: i32,
    section_count: i32,
) -> PyResult<(usize, usize, i32)> {
    let bytes: Vec<u8> = payload.as_bytes().to_vec();
    let chunk = py
        .allow_threads(move || rw::decode_chunk(&bytes, cx, cz, min_y, section_count))
        .into_py()?;
    let first_cell = chunk
        .sections
        .first()
        .map(|s| s.block_states.get(0))
        .unwrap_or(0);
    Ok((chunk.sections.len(), chunk.block_entities.len(), first_cell))
}

/// Register the `world` submodule.
pub fn register(py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new_bound(py, "world")?;
    m.add_class::<PyWorld>()?;
    m.add_function(wrap_pyfunction!(block_is_solid, &m)?)?;
    m.add_function(wrap_pyfunction!(block_is_water, &m)?)?;
    m.add_function(wrap_pyfunction!(block_name, &m)?)?;
    m.add_function(wrap_pyfunction!(decode_chunk_summary, &m)?)?;
    parent.add_submodule(&m)?;
    Ok(())
}
