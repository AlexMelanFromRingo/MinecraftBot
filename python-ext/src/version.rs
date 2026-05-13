//! Module-level identity attributes exposed on `minecraft_bot_accel`.
//!
//! * ``__version__`` — semver of the native package (read from the
//!   crate's Cargo manifest at compile time).
//! * ``python_compat`` — the ``minecraft_bot`` line this build claims
//!   parity with. CI cross-validates this against
//!   ``python/pyproject.toml``.
//! * ``implementation`` — the literal string ``"rust"`` (the Python
//!   reference exposes ``"python"``). Tests use this to tell which
//!   backend they imported.

use pyo3::prelude::*;

/// Native package version. Populated from Cargo manifest.
pub const PACKAGE_VERSION: &str = env!("CARGO_PKG_VERSION");

/// Compatible ``minecraft_bot`` (Python reference) version line.
///
/// Bumped by hand whenever the Python reference releases a new
/// MINOR. CI verifies this matches ``python/pyproject.toml`` via
/// ``tests/python/parity/test_smoke_bringup.py``.
pub const PYTHON_COMPAT: &str = "0.3.x";

/// Backend identifier — distinct from ``minecraft_bot.implementation``.
pub const IMPLEMENTATION: &str = "rust";

/// Register version attributes on the parent module.
pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.setattr("__version__", PACKAGE_VERSION)?;
    parent.setattr("python_compat", PYTHON_COMPAT)?;
    parent.setattr("implementation", IMPLEMENTATION)?;
    Ok(())
}
