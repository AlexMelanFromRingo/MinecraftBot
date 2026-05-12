//! PyO3 wrap: PyEntity mirroring `python/minecraft_bot.entities.base.Entity`.

use minecraft_bot::entities as re;
use pyo3::prelude::*;

#[pyclass(module = "minecraft_bot_accel.entities", name = "Entity")]
#[derive(Clone)]
pub struct PyEntity {
    inner: re::Entity,
}

#[pymethods]
impl PyEntity {
    #[new]
    #[pyo3(signature = (
        entity_id, type_id, x, y, z, *,
        yaw = 0.0, pitch = 0.0,
        vx = 0, vy = 0, vz = 0,
        health = None,
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        entity_id: i32,
        type_id: i32,
        x: f64,
        y: f64,
        z: f64,
        yaw: f32,
        pitch: f32,
        vx: i16,
        vy: i16,
        vz: i16,
        health: Option<f32>,
    ) -> Self {
        Self {
            inner: re::Entity {
                entity_id,
                uuid: [0u8; 16],
                type_id,
                x,
                y,
                z,
                yaw,
                pitch,
                vx,
                vy,
                vz,
                health,
            },
        }
    }

    #[getter]
    fn entity_id(&self) -> i32 {
        self.inner.entity_id
    }
    #[getter]
    fn type_id(&self) -> i32 {
        self.inner.type_id
    }
    #[getter]
    fn x(&self) -> f64 {
        self.inner.x
    }
    #[getter]
    fn y(&self) -> f64 {
        self.inner.y
    }
    #[getter]
    fn z(&self) -> f64 {
        self.inner.z
    }
    #[getter]
    fn yaw(&self) -> f32 {
        self.inner.yaw
    }
    #[getter]
    fn pitch(&self) -> f32 {
        self.inner.pitch
    }
    #[getter]
    fn vx(&self) -> i16 {
        self.inner.vx
    }
    #[getter]
    fn vy(&self) -> i16 {
        self.inner.vy
    }
    #[getter]
    fn vz(&self) -> i16 {
        self.inner.vz
    }
    #[getter]
    fn health(&self) -> Option<f32> {
        self.inner.health
    }

    fn __eq__(&self, other: &Self) -> bool {
        self.inner == other.inner
    }

    fn __repr__(&self) -> String {
        format!(
            "Entity(id={}, type_id={}, x={:.2}, y={:.2}, z={:.2})",
            self.inner.entity_id, self.inner.type_id, self.inner.x, self.inner.y, self.inner.z,
        )
    }
}

/// Register `entities` submodule.
pub fn register(py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new_bound(py, "entities")?;
    m.add_class::<PyEntity>()?;
    parent.add_submodule(&m)?;
    Ok(())
}
