//! PyO3 wrapper for `minecraft_bot::physics`.

use minecraft_bot::physics as rphys;
use pyo3::prelude::*;

use crate::world::PyWorld;

/// Bot kinematic state (mirrors `physics.PhysicsState`).
#[pyclass(module = "minecraft_bot_accel.physics", name = "PhysicsState")]
#[derive(Clone, Copy)]
pub struct PyPhysicsState {
    inner: rphys::PhysicsState,
}

#[pymethods]
impl PyPhysicsState {
    #[new]
    #[pyo3(signature = (
        x = 0.0, y = 0.0, z = 0.0,
        vx = 0.0, vy = 0.0, vz = 0.0,
        on_ground = false,
    ))]
    fn new(x: f64, y: f64, z: f64, vx: f64, vy: f64, vz: f64, on_ground: bool) -> Self {
        Self {
            inner: rphys::PhysicsState {
                x,
                y,
                z,
                vx,
                vy,
                vz,
                on_ground,
            },
        }
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
    fn vx(&self) -> f64 {
        self.inner.vx
    }
    #[getter]
    fn vy(&self) -> f64 {
        self.inner.vy
    }
    #[getter]
    fn vz(&self) -> f64 {
        self.inner.vz
    }
    #[getter]
    fn on_ground(&self) -> bool {
        self.inner.on_ground
    }

    fn __repr__(&self) -> String {
        format!(
            "PhysicsState(x={:.4}, y={:.4}, z={:.4}, vx={:.4}, vy={:.4}, vz={:.4}, on_ground={})",
            self.inner.x,
            self.inner.y,
            self.inner.z,
            self.inner.vx,
            self.inner.vy,
            self.inner.vz,
            self.inner.on_ground,
        )
    }
}

/// Per-tick movement intent (mirrors `physics.PhysicsIntent`).
#[pyclass(module = "minecraft_bot_accel.physics", name = "PhysicsIntent")]
#[derive(Clone, Copy)]
pub struct PyPhysicsIntent {
    inner: rphys::PhysicsIntent,
}

#[pymethods]
impl PyPhysicsIntent {
    #[new]
    #[pyo3(signature = (
        dx = 0.0, dz = 0.0, jump = false, sprint = false, sneak = false,
    ))]
    fn new(dx: f64, dz: f64, jump: bool, sprint: bool, sneak: bool) -> Self {
        Self {
            inner: rphys::PhysicsIntent {
                dx,
                dz,
                jump,
                sprint,
                sneak,
            },
        }
    }

    #[getter]
    fn dx(&self) -> f64 {
        self.inner.dx
    }
    #[getter]
    fn dz(&self) -> f64 {
        self.inner.dz
    }
    #[getter]
    fn jump(&self) -> bool {
        self.inner.jump
    }
    #[getter]
    fn sprint(&self) -> bool {
        self.inner.sprint
    }
    #[getter]
    fn sneak(&self) -> bool {
        self.inner.sneak
    }
}

/// Advance one physics tick (pure).
#[pyfunction]
#[pyo3(signature = (state, intent, world, *, in_water = false, in_lava = false))]
fn tick(
    state: &PyPhysicsState,
    intent: &PyPhysicsIntent,
    world: &PyWorld,
    in_water: bool,
    in_lava: bool,
) -> PyPhysicsState {
    let w = world.arc();
    let new_state = rphys::tick(&state.inner, &intent.inner, w.as_ref(), in_water, in_lava);
    PyPhysicsState { inner: new_state }
}

/// **Batched tick** — run `n_ticks` consecutive ticks in Rust without
/// crossing the FFI boundary between them. Useful for client-side
/// simulation / replay where the caller needs many ticks back-to-back.
/// Returns the final state.
#[pyfunction]
#[pyo3(signature = (state, intent, world, n_ticks, *, in_water = false, in_lava = false))]
fn tick_n(
    py: Python<'_>,
    state: &PyPhysicsState,
    intent: &PyPhysicsIntent,
    world: &PyWorld,
    n_ticks: usize,
    in_water: bool,
    in_lava: bool,
) -> PyPhysicsState {
    let w = world.arc();
    let initial = state.inner;
    let intent = intent.inner;
    let final_state = py.allow_threads(move || {
        // Hold a single read-guard over the chunk cache for the whole
        // tick batch — physics collides against is_solid repeatedly,
        // so amortising the lock pays off identically to the
        // pathfinder snapshot.
        let guard = w.query_guard();
        let collision = GuardCollision { guard: &guard };
        let mut state = initial;
        for _ in 0..n_ticks {
            state = rphys::tick(&state, &intent, &collision, in_water, in_lava);
        }
        state
    });
    PyPhysicsState { inner: final_state }
}

/// CollisionWorld adapter over a long-lived World read-guard.
struct GuardCollision<'a> {
    guard: &'a minecraft_bot::world::cache::WorldQueryGuard<'a>,
}

impl<'a> minecraft_bot::physics::CollisionWorld for GuardCollision<'a> {
    #[inline]
    fn is_solid(&self, x: i32, y: i32, z: i32) -> bool {
        self.guard.is_solid(x, y, z)
    }
}

/// Register `physics` submodule.
pub fn register(py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new_bound(py, "physics")?;
    m.add_class::<PyPhysicsState>()?;
    m.add_class::<PyPhysicsIntent>()?;
    m.add_function(wrap_pyfunction!(tick, &m)?)?;
    m.add_function(wrap_pyfunction!(tick_n, &m)?)?;
    // Constants.
    m.add("GRAVITY", rphys::GRAVITY)?;
    m.add("AIR_DRAG", rphys::AIR_DRAG)?;
    m.add("GROUND_FRICTION", rphys::GROUND_FRICTION)?;
    m.add("WATER_DRAG", rphys::WATER_DRAG)?;
    m.add("JUMP_VELOCITY", rphys::JUMP_VELOCITY)?;
    m.add("WALK_CAP", rphys::WALK_CAP)?;
    m.add("SPRINT_CAP", rphys::SPRINT_CAP)?;
    m.add("SNEAK_CAP", rphys::SNEAK_CAP)?;
    m.add("STEP_HEIGHT", rphys::STEP_HEIGHT)?;
    m.add("BBOX_W", rphys::BBOX_W)?;
    m.add("BBOX_H", rphys::BBOX_H)?;
    m.add("TERMINAL_VELOCITY", rphys::TERMINAL_VELOCITY)?;
    parent.add_submodule(&m)?;
    Ok(())
}
