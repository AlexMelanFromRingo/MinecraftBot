# Quickstart: Working on 004 Full Bot Parity

**Phase**: 1 — Design & Contracts
**Feature**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

This document is the dev workflow for 004. Read it once before you start a new method group; refer back when the parity test fails.

## One-time setup

```bash
cd /home/young-developer/my_todo/MinecraftBot
python3 -m venv .venv && source .venv/bin/activate
pip install -e python/[dev]
pip install maturin pytest pytest-asyncio pytest-benchmark
maturin develop --release --manifest-path python-ext/Cargo.toml
```

Verify all three loaders work:

```bash
python -c "
import minecraft_bot, minecraft_bot_accel
print('py', minecraft_bot.__version__, minecraft_bot.implementation)
print('accel', minecraft_bot_accel.__version__, minecraft_bot_accel.implementation)
"
cargo build --release -p minecraft_bot
```

Test server must be reachable:

```bash
nc -vz 172.26.160.1 25565
```

## The 004 implementation loop

Each method group is one PR-sized commit. The loop is:

1. **Read Python.** Open `python/minecraft_bot/bot.py` and locate the method. Read the implementation top-to-bottom. Note: every clientbound packet it consumes, every serverbound packet it emits, what state it mutates, what exceptions it raises.
2. **Port to Rust.** Add the method to the relevant `rust/src/bot/<group>.rs` file. Match the Python flow line-for-line. If a helper is missing (e.g., `recipes.rs::lookup_recipe`), add it.
3. **Wrap in accel.** Add the `#[pymethods]` / `#[getter]` in `python-ext/src/bot/<group>_py.rs`. For sync properties (accessors), use the `Python::with_gil` + `tokio handle.block_on` pattern from R-1. For async methods, use `pyo3-async-runtimes::tokio::future_into_py`.
4. **Write the parity test.** Add a row in `tests/python/parity/test_packet_trace_parity.py`. Use the standard fixture: connect Python bot, run method, capture WireLog; connect accel bot, run same method, capture WireLog; diff via `_parity_normalizer.compare(trace_py, trace_accel)`.
5. **Live test on Paper.** Run the live integration test for this method (`pytest -m live tests/python/integration/test_bot_full_parity_live.py::test_<method>`).
6. **Rust unit test.** Add a `#[tokio::test]` in `tests/rust/integration_bot_full.rs::test_<method>` gated by `#[cfg(feature = "live-smoke")]`. Run `cargo test --features live-smoke -- --test-threads=1 test_<method>`.
7. **Commit.** Message format: `004: <group>: implement <method>(...) on Rust + accel`.

## Per-group entry points

| Group | Spec FRs | Rust files | Accel files | Test files |
|---|---|---|---|---|
| State accessors | FR-001 | `bot/state.rs` | `bot/state_getters.rs` | `parity/test_accessors.py` |
| Movement | FR-002..006 | `bot/movement.rs` | `bot/movement_py.rs` | `parity/test_movement.py` |
| Combat | FR-007..009 | `bot/combat.rs` | `bot/combat_py.rs` | `parity/test_combat.py` |
| World query | FR-010..018 | `bot/world_query.rs` | `bot/world_query_py.rs` | `parity/test_world_query.py` + `perf/test_speedup_world_query.py` |
| Observation | FR-019..020 | `observation.rs` | (existing module) | `parity/test_observation.py` |
| Inventory | FR-021..032 | `bot/inventory.rs`, `inventory/*` | `bot/inventory_py.rs` | `parity/test_inventory.py` |
| Containers | FR-033..036 | `bot/containers.rs`, `recipes.rs` | `bot/containers_py.rs` | `parity/test_containers.py` |
| High-level tasks | FR-037..041 | `bot/tasks.rs`, `foods.rs` | `bot/tasks_py.rs` | `parity/test_tasks.py` |
| Behaviour trees | FR-042..044 | `behaviour/*` | `behaviour_py.rs` | `parity/test_behaviour.py` |

Implement in this order — later groups depend on earlier ones (containers depend on inventory; tasks depend on movement, combat, world query, inventory).

## Common pitfalls

- **Sync property + tokio runtime.** Always release the GIL before `block_on`: `py.allow_threads(|| handle.block_on(rust_async))`. Forgetting deadlocks the asyncio thread.
- **Inventory mutex scope.** Acquire the inventory mutex **inside** the Rust method, not outside in the accel wrapper. The accel wrapper does not know which Rust calls mutate inventory.
- **Packet-trace whitelist.** A new tolerant field requires editing `_parity_normalizer.py` and a code-review note. Do not silently expand the whitelist when a test fails — usually the bug is in the implementation.
- **Behaviour-tree leaves crossing GIL.** When a Python custom leaf is used from the accel runner, `Python::with_gil` must surround **every** `PyDict` read/write. Holding `Py<PyDict>` across an `await` panics.
- **`async-trait` Send bound.** `async fn tick(&mut self, bot: &Bot, ctx: &BehaviourCtx) -> NodeStatus` must be `Send` for the future. `bot` and `ctx` are both `Send + Sync`; if a leaf holds a non-Send field, fix the field, not the bound.
- **Recipe grid hash.** `recipes.rs` normalises `None` -> empty string before hashing. Forgetting this means `"minecraft:oak_planks"` in slot 4 with everything else `None` hashes differently from the actual recipe entry, and lookup fails silently.

## Daily commands

```bash
# Build everything (after Rust changes)
maturin develop --release --manifest-path python-ext/Cargo.toml && pip install -e python/ -q

# Parity test loop for the group you're working on
pytest tests/python/parity/test_<group>.py -v

# Full parity suite
pytest tests/python/parity -q

# Live test for one method (server must be up)
pytest -m live tests/python/integration/test_bot_full_parity_live.py::test_<method> -v

# Rust live smoke
cargo test --features live-smoke -p minecraft_bot --test integration_bot_full -- --test-threads=1

# Perf gates
pytest tests/python/perf -q

# Lint + format (run before commit)
cargo fmt --all && cargo clippy --all-targets --no-deps
ruff check python/ python-ext/ tests/python/ --fix
```

## Cutting v0.3.0

When all 60 methods are green:

1. Bump versions in `python/pyproject.toml`, `rust/Cargo.toml`, `python-ext/Cargo.toml`, `python-ext/pyproject.toml`, `python/minecraft_bot/__init__.py`, `python-ext/src/version.rs` (PYTHON_COMPAT = "0.3.x").
2. Update `CHANGELOG.md` with a v0.3.0 entry listing every newly-ported method.
3. Update README.md to remove the "subset" language — all three artefacts share the same surface.
4. Merge `004-full-bot-parity` into `main` (fast-forward).
5. Tag `v0.3.0` on the merge commit and push the tag. Wheels (003) workflow rebuilds and publishes the release with the same three artefact types as v0.2.0.

## Definition of done for 004

- Every row in `contracts/api-surface.md` has a corresponding implementation on all three backends.
- `pytest tests/python/parity -q` shows zero failures (the introspection test in particular).
- `cargo test --features live-smoke -- --test-threads=1` passes.
- `tests/python/perf/test_speedup_world_query.py` passes the >=3x gates.
- Live arena (`172.26.160.1:25565`) test session: spawn TestBot1, run every method group in sequence, no errors.
- README + CHANGELOG updated; v0.3.0 release published with 3 accel wheels + 1 Python wheel + 1 sdist + 1 Rust crate tarball.
