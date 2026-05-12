# Phase 0 Research: Rust + PyO3 framework port

**Feature**: 003-rust-pyo3-bridge
**Date**: 2026-05-12
**Status**: Complete — all NEEDS-CLARIFICATION items resolved

## R-001 — PyO3 version, ABI strategy, MSRV

**Decision**: `pyo3 = "0.22"` with features `["extension-module", "abi3-py311"]`.

**Rationale**:
- 0.22 is the current stable line as of 2026-05; it ships full async
  support via the companion `pyo3-async-runtimes` crate and has the
  most ergonomic `Bound<'py, T>` / `Py<T>` distinction.
- The `abi3-py311` feature pins the minimum supported Python and lets
  a single compiled artefact target every Python ≥ 3.11. This is the
  whole point of FR-006 (one wheel per platform).
- MSRV stays at 1.75 (existing crate baseline). PyO3 0.22 needs ≥ 1.74,
  so we're inside the floor.

**Alternatives considered**:
- `pyo3 = "0.21"`: older but pyo3-asyncio-flavoured `pyo3-async`
  ecosystem split mid-line; rejected for churn cost.
- Per-minor wheels (no abi3): rejected — multiplies wheel matrix 5×,
  needless given the cost is only a small set of removed APIs we
  don't use.
- `pyo3 = "0.23"`: pre-release at time of plan; rejected to avoid
  bleeding-edge breakage during a long milestone.

## R-002 — Async bridge between tokio and asyncio

**Decision**: `pyo3-async-runtimes` v0.22 (the successor of
`pyo3-asyncio`) with the `tokio-runtime` feature.

**Rationale**:
- Resolved in spec.md Clarifications Q3.
- Cross-registers the existing tokio runtime (which `rust/connection.rs`
  already uses) and the host asyncio event loop so that
  `future_into_py(py, async move { ... })` returns a Python awaitable
  that resumes the asyncio loop instead of blocking it.
- Provides `into_future` for converting Python coroutines into Rust
  futures — needed if the native Bot ever awaits a Python hook.

**Alternatives considered**:
- Custom Future bridge via `tokio::sync::oneshot` + `loop.call_soon_threadsafe`:
  rejected — easy to get cancellation, exception propagation, and
  loop-shutdown wrong; pyo3-async-runtimes has these solved.
- Sync API only (`bot.connect_sync()`): rejected — breaks
  `SC-007` (substitution requires only an import change). The Python
  reference is `async`; the native package must be too.

**Risks**:
- pyo3-async-runtimes registers a tokio runtime at process scope.
  We must ensure only one runtime is created; the façade will use the
  `tokio_runtime!` macro and a OnceLock guard.
- Cancellation semantics: a Python-side `asyncio.CancelledError` should
  translate to dropping the Rust future. pyo3-async-runtimes does this
  via `cancel_on_drop`; we validate in a dedicated test.

## R-003 — Wheel build pipeline (maturin matrix)

**Decision**: `maturin` ≥ 1.5 invoked via the `PyO3/maturin-action`
GitHub Action. Matrix:

| OS | Arch | Build host | Strategy |
|----|------|------------|----------|
| Linux | x86_64 | ubuntu-latest | native build in manylinux2014 container |
| Linux | aarch64 | ubuntu-latest | cross-compile via `aarch64-unknown-linux-gnu` |
| macOS | arm64 | macos-latest (M-series) | native build |
| macOS | x86_64 | macos-latest | `--target x86_64-apple-darwin` cross |
| Windows | x86_64 | windows-latest | native build |

One wheel per (OS, arch), abi3 — no per-Python-minor split.

**Rationale**:
- The `PyO3/maturin-action` is the maintainer-recommended path and
  handles manylinux container setup automatically.
- ubuntu-latest for aarch64 via QEMU/cross is acceptable for build
  time (~15 min) — alternative would be self-hosted ARM runners,
  out of scope for this project.
- `manylinux2014` (glibc 2.17+) covers RHEL/CentOS 7+, Debian 8+,
  Ubuntu 18.04+ — broad enough.

**Alternatives considered**:
- `cibuildwheel`: rejected — designed for setuptools-style projects;
  maturin is the native PyO3 path.
- Self-hosted ARM macOS runners for native cross builds: rejected — no
  ROI for current scale.
- Single-platform pre-release (Linux x86_64 only): rejected — fails
  FR-007 (must ship 5 platforms).

## R-004 — Pyclass strategy for public-type contract

**Decision**: Each public dataclass in `minecraft_bot` gets a peer
`#[pyclass(name = "...", get_all)]` struct in `python-ext/src/` with:
- Identical field names + types (Python int ↔ Rust i64/i32 by context).
- `#[pymethods] fn __repr__` returning a string matching the Python
  reference's `repr()`.
- `#[pymethods] fn __eq__` for value equality (parity tests rely on this).
- `from_dict` / `to_dict` round-trippers for ML pipelines (matches
  002's API).

No cross-package imports. `isinstance(o, mb.Observation)` and
`isinstance(o, mb_accel.Observation)` are independent class objects.
Parity tests compare fields, not types.

**Rationale**:
- Resolved in spec.md Clarifications Q4. Keeps Constitution VI
  invariant (`minecraft_bot` has zero deps; never imports accel).
- `get_all` auto-exposes every field as a Python property — no manual
  getter boilerplate.

**Alternatives considered**:
- Shared `typing.Protocol`s in a third tiny package: rejected — adds
  a dep to the Python reference.
- Re-use the Python reference's dataclasses by importing them in
  `accel`: rejected for the same Constitution VI reason.
- Returning plain `dict` from every native call: rejected — breaks
  `bot.observation().position` attribute access and the PyTorch-style
  surface (Principle III).

## R-005 — GIL release strategy

**Decision**: Two-tier policy:

1. **CPU-bound > 10 µs sections** (chunk decode, NBT decode of large
   payloads, pathfinding inner loop, packet batch decode) wrap their
   pure-compute core in `py.allow_threads(|| { ... })`.
2. **Trivial reads** (varint single read, struct field access on a
   `#[pyclass]`) keep the GIL — the cost of release/re-acquire would
   exceed the saved compute.

**Rationale**:
- FR-012 demands GIL release on long compute.
- Pathfinding takes no Python callbacks (Q4 resolved type-sharing;
  World cache lives entirely in Rust on the native side per FR-021), so
  the GIL can stay released for the whole search.
- Chunk decode and NBT decode similarly operate on borrowed `&[u8]`;
  no Python objects touched until the result is constructed.

**Alternatives considered**:
- Release-everything: rejected — overhead for fast paths.
- Release-nothing: rejected — fails FR-012; blocks multi-bot CPU
  scaling (SC-013).

## R-006 — Cross-check tool extension

**Decision**: Extend `tools/cross_check.py` with a `--backend
accel` mode that imports `minecraft_bot_accel` and calls its codec
entry points alongside Python's. The shared driver runs each fixture
through three encoders (python, rust-cli, accel) and asserts all three
hashes match.

**Rationale**:
- The existing cross-check already drives Python and Rust (via the
  `cross_check_rust` binary in `rust/examples/`). Adding a third
  in-process encoder is straightforward.
- Catches every accel-side codec regression on every CI run — the
  cheapest possible parity gate.

**Alternatives considered**:
- Three separate CI jobs comparing pair-wise: rejected — easier to
  spot a divergence when all three are next to each other on the
  same fixture.

## R-007 — Test parametrisation across backends

**Decision**: Add a session-scoped pytest fixture in
`tests/python/conftest.py`:

```python
# tests/python/conftest.py
import importlib
import pytest

def pytest_addoption(parser):
    parser.addoption("--backend", choices=["python", "accel"],
                     default="python")

@pytest.fixture(scope="session")
def backend(pytestconfig):
    name = pytestconfig.getoption("--backend")
    return importlib.import_module(
        "minecraft_bot" if name == "python" else "minecraft_bot_accel"
    )
```

Existing tests that do `from minecraft_bot import Bot` are migrated
to a thin helper `from tests.helpers import Bot` (or accept `backend`
as a fixture argument). CI runs `pytest --backend python` and
`pytest --backend accel` in parallel jobs.

**Rationale**:
- FR-017: both backends MUST pass the same suite.
- Single source of test code → no drift, no copy-paste.
- The migration is mechanical and can be scripted (sed/codemod).

**Alternatives considered**:
- Two separate test trees: rejected — drift risk + 2× maintenance.
- Monkeypatch sys.modules in conftest to swap `minecraft_bot` →
  `minecraft_bot_accel`: rejected — masks real import-time bugs;
  explicit injection is safer.

## R-008 — Rust-side Bot-API port: scope and patterns

**Decision**: Mirror the Python module tree under `rust/src/` with the
following module-by-module strategy:

| Python module | Rust port | Notes |
|---|---|---|
| `world/cache.py` | `rust/src/world/cache.rs` | DashMap<ChunkPos, Chunk>; same eviction policy |
| `world/chunk.py` | `rust/src/world/chunk.rs` | 16×16×N section grid |
| `world/decode_chunk.py` | `rust/src/world/decode_chunk.rs` | paletted-container parser |
| `observation.py` | `rust/src/observation.rs` | snapshot from Connection state |
| `pathfinding.py` | `rust/src/pathfinding/{astar,walkable}.rs` | A* + walkable graph builder |
| `physics.py` | `rust/src/physics.rs` | 20 Hz tick, water/slab/ledge math |
| `behaviour/walk_to.py` | `rust/src/behaviour/walk_to.rs` | path-follow loop, 5-block anti-cheat cap |
| `behaviour/hazards.py` | `rust/src/behaviour/hazards.rs` | slab/water/ledge/drop detector |
| `inventory_click.py` | `rust/src/behaviour/window_click.rs` | drop/pickup window-click flow |
| `bot.py` | `rust/src/bot.rs` | top-level facade over the above |

Behavioural parity is established with cross-language tests in
`rust/tests/` that feed identical inputs to both implementations and
compare outputs (positions, packets emitted, observations).

**Rationale**:
- One-to-one module mapping makes the diff between the two
  implementations easy to audit (Constitution Principle I).
- `DashMap` is a small dep, but it's BSD-licensed and standard for
  this pattern. Alternative `RwLock<HashMap>` works too — we'll
  pick at implementation time based on contention measurements.

**Alternatives considered**:
- Wrap Python objects directly via PyO3 callbacks instead of
  porting: rejected — that's the overlay-ascelerator design we
  explicitly rejected in Q1.
- Async-everything in Rust World cache: rejected — World ops are CPU,
  not I/O; sync RwLock fits better.

## R-009 — WireLog format invariance

**Decision**: The accel `WireLog` MUST write byte-identical JSONL to
the same path the Python WireLog writes. Schema is the existing
`{"ts":..., "dir":"rx|tx", "name":"...", "raw":"hex"}` plus the
schema-version-1 meta header.

**Rationale**:
- Constitution VII demands replayability. A capture from the accel
  backend must replay through the Python reference (and vice versa)
  so we can debug accel bugs by routing the bytes through Python's
  decoder.
- A diff between accel and python WireLogs of the same session is
  a strong regression sentinel.

**Acceptance test**: capture a 30-second session under each backend,
diff the WireLogs — should be identical modulo timestamps.

## R-010 — Versioning and release coordination

**Decision**:
- `minecraft_bot` (Python reference) keeps semver in `python/pyproject.toml`.
- `minecraft_bot_accel` ships an **independent** semver. Major bumps
  coordinated with `minecraft_bot` major bumps; minor/patch are free.
- `minecraft_bot_accel.__version__` is exposed at module level.
  `minecraft_bot_accel.python_compat = "1.x"` declares which
  `minecraft_bot` line it claims parity with. CI verifies this matches
  before greenlighting a release.

**Rationale**:
- Decouples release cadence (the accel package may need patch releases
  for build-pipeline issues that don't affect the Python reference)
  while keeping the parity contract enforceable.

## R-011 — Wheel size + startup-time budget

**Decision**:
- Per-platform wheel target: ≤ 5 MiB compressed.
- Cold-import `import minecraft_bot_accel` time: ≤ 100 ms on a Linux
  laptop.
- LTO: thin (already in `rust/Cargo.toml`).

**Rationale**:
- Soft budgets — informational, monitored in CI but not blocking.
- Keeps wheel installs fast on slow links.

## R-012 — Cancellation, panics, and exception types

**Decision**:
- All `#[pyfunction]`/`#[pymethod]` returns `PyResult<T>`; Rust
  errors map to the Python reference's exception types via a
  central `PyErr` translation layer in `python-ext/src/errors.rs`.
- `panic!` in Rust is caught by PyO3 and converted to
  `PanicException`, but we treat any panic as a bug — there is a
  `RUST_BACKTRACE=1` test that runs the suite and asserts no panics.
- `asyncio.CancelledError` propagates into Rust as a `JoinError` /
  `Cancelled` that the bridge converts back to `CancelledError` on
  the Python side. The `tick_loop` task aborts cleanly on cancel.

**Rationale**:
- Constitution VII (observability) needs precise error semantics;
  generic `RuntimeError` from a panic eats debugging info.

## Outstanding items deferred to /speckit-tasks

- Concrete maturin matrix YAML — included in tasks T0xx but not
  expanded here.
- Bench-comparison thresholds for soft regression detection — set
  empirically when first bench data lands.
- aarch64 cross-build container choice (manylinux2014_aarch64 vs
  manylinux_2_28_aarch64) — pick at first wheel build.
