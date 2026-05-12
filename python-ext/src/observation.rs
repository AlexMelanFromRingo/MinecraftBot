//! PyO3 wraps: PyVec3 + PyObservation. Mirror Python's
//! `minecraft_bot.observation.{RayHit, Observation}` field shapes.

use minecraft_bot::observation as ro;
use pyo3::prelude::*;
use pyo3::types::PyDict;

/// 3D vector.
#[pyclass(module = "minecraft_bot_accel.observation", name = "Vec3")]
#[derive(Clone, Copy)]
pub struct PyVec3 {
    inner: ro::Vec3,
}

#[pymethods]
impl PyVec3 {
    #[new]
    fn new(x: f64, y: f64, z: f64) -> Self {
        Self { inner: ro::Vec3::new(x, y, z) }
    }
    #[getter] fn x(&self) -> f64 { self.inner.x }
    #[getter] fn y(&self) -> f64 { self.inner.y }
    #[getter] fn z(&self) -> f64 { self.inner.z }

    fn __repr__(&self) -> String {
        format!("Vec3({}, {}, {})", self.inner.x, self.inner.y, self.inner.z)
    }

    fn __eq__(&self, other: &Self) -> bool {
        self.inner == other.inner
    }

    fn to_dict<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new_bound(py);
        d.set_item("x", self.inner.x)?;
        d.set_item("y", self.inner.y)?;
        d.set_item("z", self.inner.z)?;
        Ok(d)
    }

    fn as_tuple(&self) -> (f64, f64, f64) {
        (self.inner.x, self.inner.y, self.inner.z)
    }
}

/// Compact bot observation snapshot.
#[pyclass(module = "minecraft_bot_accel.observation", name = "Observation")]
#[derive(Clone)]
pub struct PyObservation {
    inner: ro::Observation,
}

#[pymethods]
impl PyObservation {
    #[new]
    #[pyo3(signature = (
        x = 0.0, y = 0.0, z = 0.0,
        yaw = 0.0, pitch = 0.0, on_ground = false,
        health = 20.0, food = 20, saturation = 5.0,
    ))]
    fn new(
        x: f64, y: f64, z: f64,
        yaw: f32, pitch: f32, on_ground: bool,
        health: f32, food: i32, saturation: f32,
    ) -> Self {
        Self {
            inner: ro::Observation {
                x, y, z, yaw, pitch, on_ground, health, food, saturation,
            },
        }
    }

    #[getter] fn x(&self) -> f64 { self.inner.x }
    #[getter] fn y(&self) -> f64 { self.inner.y }
    #[getter] fn z(&self) -> f64 { self.inner.z }
    #[getter] fn yaw(&self) -> f32 { self.inner.yaw }
    #[getter] fn pitch(&self) -> f32 { self.inner.pitch }
    #[getter] fn on_ground(&self) -> bool { self.inner.on_ground }
    #[getter] fn health(&self) -> f32 { self.inner.health }
    #[getter] fn food(&self) -> i32 { self.inner.food }
    #[getter] fn saturation(&self) -> f32 { self.inner.saturation }

    fn __eq__(&self, other: &Self) -> bool {
        self.inner == other.inner
    }

    fn __repr__(&self) -> String {
        format!(
            "Observation(x={:.2}, y={:.2}, z={:.2}, yaw={:.1}, pitch={:.1}, \
             on_ground={}, health={:.1}, food={}, saturation={:.1})",
            self.inner.x, self.inner.y, self.inner.z,
            self.inner.yaw, self.inner.pitch, self.inner.on_ground,
            self.inner.health, self.inner.food, self.inner.saturation,
        )
    }

    fn to_dict<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new_bound(py);
        d.set_item("x", self.inner.x)?;
        d.set_item("y", self.inner.y)?;
        d.set_item("z", self.inner.z)?;
        d.set_item("yaw", self.inner.yaw)?;
        d.set_item("pitch", self.inner.pitch)?;
        d.set_item("on_ground", self.inner.on_ground)?;
        d.set_item("health", self.inner.health)?;
        d.set_item("food", self.inner.food)?;
        d.set_item("saturation", self.inner.saturation)?;
        Ok(d)
    }
}

/// Register the `observation` submodule.
pub fn register(py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new_bound(py, "observation")?;
    m.add_class::<PyVec3>()?;
    m.add_class::<PyObservation>()?;
    parent.add_submodule(&m)?;
    Ok(())
}
