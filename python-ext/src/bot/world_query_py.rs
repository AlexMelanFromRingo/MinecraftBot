//! Accel async wrappers for Group D world-query methods (T040):
//! find_blocks_nearby, raycast, scan_volume, voxel_grid,
//! chunks_around, world_map_3d, nearby_entities, nearby_players,
//! distance_to.

use std::sync::Arc;

use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;

use super::PyBot;

#[pymethods]
impl PyBot {
    /// `find_blocks_nearby(name, *, radius=32, limit=16) -> list[tuple]`.
    #[pyo3(signature = (name, *, radius = 32, limit = 16))]
    fn find_blocks_nearby<'py>(
        &self,
        py: Python<'py>,
        name: String,
        radius: i32,
        limit: usize,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            Ok(bot.find_blocks_nearby(&name, radius, limit).await)
        })
    }

    /// `nearby_entities(*, radius=32.0, type_filter=None) -> list[(eid, type_id, (x, y, z))]`.
    /// `type_filter` accepted for Python sig parity but ignored on accel
    /// (filter the returned list in Python).
    #[pyo3(signature = (*, radius = 32.0, type_filter = None))]
    fn nearby_entities<'py>(
        &self,
        py: Python<'py>,
        radius: f64,
        type_filter: Option<PyObject>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let _ = type_filter;
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            let entities = bot.nearby_entities(radius).await;
            Ok(entities
                .into_iter()
                .map(|e| (e.entity_id, e.type_id, (e.x, e.y, e.z)))
                .collect::<Vec<_>>())
        })
    }

    /// `nearby_players(*, radius=32.0) -> list[(eid, type_id, (x, y, z))]`.
    #[pyo3(signature = (*, radius = 32.0))]
    fn nearby_players<'py>(
        &self,
        py: Python<'py>,
        radius: f64,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            let players = bot.nearby_players(radius).await;
            Ok(players
                .into_iter()
                .map(|e| (e.entity_id, e.type_id, (e.x, e.y, e.z)))
                .collect::<Vec<_>>())
        })
    }

    /// `distance_to(eid) -> Optional[float]`.
    fn distance_to<'py>(&self, py: Python<'py>, eid: i32) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            Ok(bot.distance_to(eid).await)
        })
    }

    /// `raycast(*, max_distance=32.0) -> Optional[(x, y, z, state_id, face)]`.
    #[pyo3(signature = (*, max_distance = 32.0))]
    fn raycast<'py>(
        &self,
        py: Python<'py>,
        max_distance: f64,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            Ok(bot.raycast(max_distance).await)
        })
    }

    /// `scan_volume(*, radius=8, include_air=False) -> list[(x, y, z, state_id)]`.
    #[pyo3(signature = (*, radius = 8, include_air = false))]
    fn scan_volume<'py>(
        &self,
        py: Python<'py>,
        radius: i32,
        include_air: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            Ok(bot.scan_volume(radius, include_air).await)
        })
    }

    /// `voxel_grid(*, radius=4) -> (flat_grid, side)`.
    #[pyo3(signature = (*, radius = 4))]
    fn voxel_grid<'py>(&self, py: Python<'py>, radius: i32) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            Ok(bot.voxel_grid(radius).await)
        })
    }

    /// `chunks_around(*, radius_chunks=2) -> list[(cx, cz)]`.
    #[pyo3(signature = (*, radius_chunks = 2))]
    fn chunks_around<'py>(
        &self,
        py: Python<'py>,
        radius_chunks: i32,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            Ok(bot.chunks_around(radius_chunks).await)
        })
    }

    /// `world_map_3d(*, radius_xz=16, radius_y=None) -> (flat_grid, (sx, sy, sz))`.
    #[pyo3(signature = (*, radius_xz = 16, radius_y = None))]
    fn world_map_3d<'py>(
        &self,
        py: Python<'py>,
        radius_xz: i32,
        radius_y: Option<i32>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            Ok(bot.world_map_3d(radius_xz, radius_y).await)
        })
    }
}
