//! PyO3 wrapper for `minecraft_bot::pathfinding`.

use minecraft_bot::pathfinding::{find_path as rust_find_path, Path};
use pyo3::prelude::*;
use pyo3::types::{PyList, PyTuple};

use crate::errors::NoPathFound;
use crate::world::PyWorld;

/// `find_path(world, start, goal, *, max_fall=3, max_nodes=100_000)`
///
/// Returns a list of (x, y, z) tuples. Raises
/// `minecraft_bot_accel.errors.NoPathFound` if unreachable / budget
/// exhausted.
#[pyfunction]
#[pyo3(signature = (world, start, goal, *, max_fall = 3, max_nodes = 100_000))]
fn find_path<'py>(
    py: Python<'py>,
    world: &PyWorld,
    start: (i32, i32, i32),
    goal: (i32, i32, i32),
    max_fall: i32,
    max_nodes: usize,
) -> PyResult<Bound<'py, PyList>> {
    let w = world.arc();
    let result: Result<Path, _> = py.allow_threads(|| {
        // Hold a single read-guard for the whole search so each
        // is_solid/is_water call is a plain HashMap::get with no
        // per-cell lock acquisition (5×+ speedup on dense queries).
        let guard = w.query_guard();
        rust_find_path(&guard, start, goal, max_fall, max_nodes)
    });
    match result {
        Ok(path) => {
            let list = PyList::empty_bound(py);
            for (x, y, z) in path.nodes {
                list.append(PyTuple::new_bound(py, [x, y, z]))?;
            }
            Ok(list)
        }
        Err(e) => Err(NoPathFound::new_err(format!("{}", e))),
    }
}

/// Register `pathfinding` submodule.
pub fn register(py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new_bound(py, "pathfinding")?;
    m.add_function(wrap_pyfunction!(find_path, &m)?)?;
    parent.add_submodule(&m)?;
    Ok(())
}
