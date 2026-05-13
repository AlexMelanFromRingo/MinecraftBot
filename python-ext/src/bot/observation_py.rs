//! Accel async wrappers for snapshot / observation (T044).
//! Each returns a Python `dict` so users don't need to import a
//! dedicated wrapper class.

use std::sync::Arc;

use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3_async_runtimes::tokio::future_into_py;

use super::PyBot;

#[pymethods]
impl PyBot {
    /// `snapshot(*, nearby_radius=32.0) -> dict`.
    #[pyo3(signature = (*, nearby_radius = 32.0))]
    fn snapshot<'py>(&self, py: Python<'py>, nearby_radius: f64) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            let snap = bot.snapshot(nearby_radius).await;
            Python::with_gil(|py| -> PyResult<PyObject> {
                let d = PyDict::new_bound(py);
                d.set_item("position", snap.position)?;
                d.set_item("orientation", snap.orientation)?;
                d.set_item("on_ground", snap.on_ground)?;
                d.set_item("health", snap.health)?;
                d.set_item("food", snap.food)?;
                d.set_item("saturation", snap.saturation)?;
                d.set_item("held_slot", snap.held_slot)?;
                let ents: Vec<(i32, i32, (f64, f64, f64))> = snap
                    .nearby_entities
                    .into_iter()
                    .map(|e| (e.entity_id, e.type_id, (e.x, e.y, e.z)))
                    .collect();
                d.set_item("nearby_entities", ents)?;
                Ok(d.unbind().into())
            })
        })
    }

    /// `observation(*, voxel_radius=4, nearby_radius=16.0, look_distance=32.0) -> dict`.
    #[pyo3(signature = (*, voxel_radius = 4, nearby_radius = 16.0, look_distance = 32.0))]
    fn observation<'py>(
        &self,
        py: Python<'py>,
        voxel_radius: i32,
        nearby_radius: f64,
        look_distance: f64,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = Arc::clone(&self.inner);
        future_into_py(py, async move {
            let bot = inner.lock().await;
            let obs = bot
                .observation(voxel_radius, nearby_radius, look_distance)
                .await;
            Python::with_gil(|py| -> PyResult<PyObject> {
                let d = PyDict::new_bound(py);
                d.set_item("position", obs.position)?;
                d.set_item("orientation", obs.orientation)?;
                d.set_item("health", obs.health)?;
                d.set_item("food", obs.food)?;
                d.set_item("voxel_grid", obs.voxel_grid)?;
                d.set_item("voxel_shape", obs.voxel_shape)?;
                d.set_item("look_hit", obs.look_hit)?;
                let ents: Vec<(i32, i32, (f64, f64, f64))> = obs
                    .nearby_entities
                    .into_iter()
                    .map(|e| (e.entity_id, e.type_id, (e.x, e.y, e.z)))
                    .collect();
                d.set_item("nearby_entities", ents)?;
                Ok(d.unbind().into())
            })
        })
    }
}
