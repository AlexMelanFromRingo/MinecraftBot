//! PyO3 wraps: PyEffectEntry mirroring `python/minecraft_bot.status_effects.EffectEntry`.

use minecraft_bot::effects as re;
use pyo3::prelude::*;

#[pyclass(module = "minecraft_bot_accel.effects", name = "StatusEffect")]
#[derive(Clone, Copy)]
pub struct PyEffectEntry {
    inner: re::EffectEntry,
}

#[pymethods]
impl PyEffectEntry {
    #[new]
    #[pyo3(signature = (id, amplifier, duration_ticks, *, is_ambient = false, show_particles = true, show_icon = true))]
    fn new(
        id: i32,
        amplifier: i32,
        duration_ticks: i32,
        is_ambient: bool,
        show_particles: bool,
        show_icon: bool,
    ) -> Self {
        Self {
            inner: re::EffectEntry {
                id,
                amplifier,
                duration_ticks,
                is_ambient,
                show_particles,
                show_icon,
            },
        }
    }

    #[getter]
    fn id(&self) -> i32 {
        self.inner.id
    }
    #[getter]
    fn amplifier(&self) -> i32 {
        self.inner.amplifier
    }
    #[getter]
    fn duration_ticks(&self) -> i32 {
        self.inner.duration_ticks
    }
    #[getter]
    fn is_ambient(&self) -> bool {
        self.inner.is_ambient
    }
    #[getter]
    fn show_particles(&self) -> bool {
        self.inner.show_particles
    }
    #[getter]
    fn show_icon(&self) -> bool {
        self.inner.show_icon
    }

    /// Canonical name (`"speed"`) or `"effect_{id}"` for unknown ids.
    #[getter]
    fn name(&self) -> String {
        self.inner.name()
    }

    /// Display level (`amplifier + 1`).
    #[getter]
    fn level(&self) -> i32 {
        self.inner.level()
    }

    fn __eq__(&self, other: &Self) -> bool {
        self.inner == other.inner
    }

    fn __repr__(&self) -> String {
        format!(
            "StatusEffect(name={:?}, level={}, duration_ticks={})",
            self.inner.name(),
            self.inner.level(),
            self.inner.duration_ticks,
        )
    }
}

/// Register `effects` submodule with helpers + class.
pub fn register(py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new_bound(py, "effects")?;
    m.add_class::<PyEffectEntry>()?;
    // Free functions.
    #[pyfunction]
    fn effect_name(id: i32) -> Option<&'static str> {
        re::effect_name(id)
    }
    #[pyfunction]
    fn effect_id(name: &str) -> Option<i32> {
        re::effect_id(name)
    }
    m.add_function(wrap_pyfunction!(effect_name, &m)?)?;
    m.add_function(wrap_pyfunction!(effect_id, &m)?)?;
    parent.add_submodule(&m)?;
    Ok(())
}
