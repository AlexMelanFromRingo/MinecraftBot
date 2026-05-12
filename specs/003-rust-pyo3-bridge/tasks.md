---
description: "Task breakdown for 003-rust-pyo3-bridge — Rust + PyO3 framework port"
---

# Tasks: Rust + PyO3 framework port

**Input**: Design documents under `/specs/003-rust-pyo3-bridge/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/api-surface.md`, `quickstart.md` — all present.

**Tests**: REQUIRED — Constitution V (live integration testing) and the
spec's parity user stories (US3) demand TDD-style parity tests before
the corresponding implementation lands. Test tasks are included in
each user-story phase.

**Organization**: Tasks are grouped by user story so each can be
implemented, tested, and merged independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1…US5)
- File paths are absolute-from-repo-root, e.g. `python-ext/src/lib.rs`.

## Path Conventions

- Python reference: `python/minecraft_bot/` — **unchanged**
- Rust standalone crate: `rust/src/` — **expanded**
- PyO3 façade crate: `python-ext/` — **new**
- Tests: `tests/python/` (parametrised) + `rust/tests/` (cargo)
- CI: `.github/workflows/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Bring up the `python-ext/` PyO3 façade crate, the maturin
build, and the cross-backend test harness. After this phase, an empty
`minecraft_bot_accel` module installs cleanly and pytest can be
parametrised over the two backends.

- [X] T001 Create directory `python-ext/` with subdirectories `src/`, `minecraft_bot_accel/`, and `python-ext/.gitignore` excluding `target/` and `*.so`
- [X] T002 Write `python-ext/Cargo.toml` declaring `name = "minecraft_bot_accel"`, `crate-type = ["cdylib"]`, path-dependency on `../rust` (the `minecraft_bot` crate), and dependencies `pyo3 = { version = "0.22", features = ["extension-module", "abi3-py311"] }` and `pyo3-async-runtimes = { version = "0.22", features = ["tokio-runtime"] }`
- [X] T003 Write `python-ext/pyproject.toml` with `[build-system] requires = ["maturin>=1.5"] build-backend = "maturin"`; project metadata `name = "minecraft_bot_accel"`, `requires-python = ">=3.11"`, classifiers, license, authors mirroring `python/pyproject.toml`; `[tool.maturin] features = ["pyo3/extension-module"] python-source = "."` so the `minecraft_bot_accel/` python folder is packaged alongside the cdylib
- [X] T004 Write `python-ext/src/lib.rs` with an empty `#[pymodule] fn minecraft_bot_accel(_py: Python, _m: Bound<PyModule>) -> PyResult<()> { Ok(()) }` so `maturin develop` succeeds end-to-end
- [X] T005 Write `python-ext/minecraft_bot_accel/__init__.py` that does `from .minecraft_bot_accel import *` and re-exports submodules registered from Rust
- [X] T006 [P] Add a top-level `Cargo.toml` workspace at the repo root (`/home/young-developer/my_todo/MinecraftBot/Cargo.toml`) listing members `["rust", "python-ext"]`, with a `[profile.release]` mirroring `rust/Cargo.toml` (lto=thin, codegen-units=1)
- [X] T007 [P] Update `.gitignore` at the repo root to exclude `python-ext/target/`, `python-ext/*.egg-info/`, `python-ext/dist/`, `python-ext/build/`, and `*.whl`
- [X] T008 [P] Add `maturin` to `python/pyproject.toml` `[project.optional-dependencies].dev` so a dev install pulls the wheel-builder
- [X] T009 Create `tests/python/conftest.py` with a session-scoped `backend` fixture and a `--backend` CLI option (values: `python`, `accel`; default `python`), as designed in research.md R-007
- [X] T010 [P] Create `tests/helpers/__init__.py` and `tests/helpers/backend.py` exposing a `Bot`, `Connection`, `Reader`, `Writer`, `WireLog` symbol indexed by the active backend fixture; existing tests that do `from minecraft_bot import Bot` migrate to `from tests.helpers.backend import Bot`
- [X] T011 Run `maturin develop --manifest-path python-ext/Cargo.toml` once and verify `python -c "import minecraft_bot_accel; print(minecraft_bot_accel.__doc__)"` returns without error — this proves the toolchain bring-up is correct before any logic lands

**Checkpoint**: empty native package importable; conftest backend fixture in place; existing Python tests pass under `--backend python`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cross-cutting infrastructure every user story depends on
— exception translation, async bridge bootstrap, public-version
attributes, registration-glue patterns. After this phase, the Rust
crate can grow new modules and the façade can register them with a
consistent error/async story.

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

- [X] T012 Create `python-ext/src/errors.rs` defining `pyo3::create_exception!` instances for `MinecraftBotError`, `ProtocolError`, `DecodeError`, `EncodeError`, `OversizedVarInt`, `ConnectionError`, `DisconnectedError`, `KickError`, `LoginError`, `TimeoutError` (subclass hierarchy per `contracts/api-surface.md`); register them on the `minecraft_bot_accel.errors` submodule
- [X] T013 Create `python-ext/src/error_map.rs` with a single `From<minecraft_bot::errors::Error> for PyErr` impl that maps every Rust-side error variant to the matching exception class from T012; ensure no path returns a generic `RuntimeError`
- [X] T014 [P] Create `python-ext/src/runtime.rs` that initialises the tokio runtime once via `OnceLock<tokio::runtime::Runtime>` and registers it with `pyo3_async_runtimes::tokio` so every async pyfunction can call `future_into_py(py, async move { ... })`
- [X] T015 [P] Create `python-ext/src/version.rs` exposing module-level `__version__`, `python_compat`, and `implementation = "rust"` attributes; pull `__version__` from the `python-ext/Cargo.toml` package version and `python_compat` from a const string that CI cross-validates against `python/pyproject.toml` (Constitution Principle I, R-010)
- [X] T016 Wire T012–T015 into `python-ext/src/lib.rs`: register the `errors` submodule, expose `__version__`/`python_compat`/`implementation` on the root, call `runtime::init_once()` at module-load
- [X] T017 [P] Create `python-ext/src/wire_log.rs` PyO3 `#[pyclass] PyWireLog` wrapping `minecraft_bot::wire_log::WireLog`; expose `to_jsonl(path)` classmethod, `append`, `flush`, `close` methods; emit JSONL byte-identical to the Python reference (R-009)
- [X] T018 [P] Add `python-ext/src/codec/mod.rs` registering `varint`, `varlong`, `nbt`, `bitset`, `slot`, `chat_component`, `identifier`, `position`, `string_codec`, `uuid_codec` as submodules; each submodule exposes `read` / `write` `#[pyfunction]`s delegating to the existing `minecraft_bot::codec::*` functions
- [X] T019 [P] Add `python-ext/src/framer.rs` `#[pyclass] PyFramer` wrapping `minecraft_bot::framer::Framer`; expose `encode_frame`, `decode_frame`, `set_compression` per `contracts/api-surface.md`
- [X] T020 Register codec, framer, errors, wire_log submodules on the root `#[pymodule]` in `python-ext/src/lib.rs`
- [X] T021 Add `tests/python/parity/__init__.py` and `tests/python/parity/test_smoke_bringup.py` that imports both backends, checks `implementation` attributes, and asserts `python_compat` matches the Python reference's `__version__` line — this is the first parity test gate
- [X] T022 [P] Update `rust/Cargo.toml` to compile cleanly as a workspace member (no edits expected; verify only)
- [X] T023 Run `pytest tests/python/parity/test_smoke_bringup.py` under both `--backend python` and `--backend accel`; both must pass before moving on

**Checkpoint**: cross-cutting infrastructure ready. New PyO3 modules added in user-story phases just plug into this scaffold.

---

## Phase 3: User Story 1 — Native-backed Bot, same public API (P1) 🎯 MVP

**Goal**: A user who changes their top-level import from
`minecraft_bot` to `minecraft_bot_accel` gets a working bot with
identical observable behaviour against the live Paper server. Every
public Bot/World/Connection/codec/protocol surface from
`contracts/api-surface.md` is available on the native side.

**Independent Test**: Run `tests/python/parity/test_us1_substitution.py`
against the live Paper server with both backends connected in
sequence; both bots reach spawn, walk to the arena, drop an item,
and disconnect cleanly with field-level position parity within
0.5 blocks.

### Rust standalone crate — port 002 bot-API into `rust/src/`

- [X] T024 [P] [US1] Create `rust/src/world/mod.rs` and port `python/minecraft_bot/world/chunk.py` → `rust/src/world/chunk.rs` (Chunk + ChunkSection structs, section grid 16×16×N, `non_air_count`, biome storage)
- [X] T025 [P] [US1] Port `python/minecraft_bot/world/decode_chunk.py` → `rust/src/world/decode_chunk.rs` (paletted-container decode for block-states and biomes; light arrays)
- [X] T026 [US1] Port `python/minecraft_bot/world/cache.py` → `rust/src/world/cache.rs` using `parking_lot::RwLock<HashMap<(i32,i32), Chunk>>` (or DashMap — pick by benchmark in implementation); same eviction policy as Python
- [X] T027 [P] [US1] Port `python/minecraft_bot/world/block_table.py` → `rust/src/world/block_table.rs` (Block struct, is_solid/is_water tables from `protocol-data/v763/`)
- [X] T028 [P] [US1] Port `python/minecraft_bot/slots.py` → `rust/src/slots.rs` (ItemStack with item_id, count, nbt)
- [ ] T029 [P] [US1] Port `python/minecraft_bot/entities/*.py` → `rust/src/entities/` (Entity struct, EntityMetadata schema decoder)
- [X] T030 [P] [US1] Port `python/minecraft_bot/status_effects.py` → `rust/src/effects.rs`
- [ ] T031 [US1] Port `python/minecraft_bot/observation.py` → `rust/src/observation.rs` (Observation snapshot builder from cache + connection state); fields per `data-model.md` parity table
- [X] T032 [P] [US1] Port `python/minecraft_bot/pathfinding.py` walkable-graph builder → `rust/src/pathfinding/walkable.rs`
- [X] T033 [US1] Port `python/minecraft_bot/pathfinding.py` A* core → `rust/src/pathfinding/astar.rs`; expose `find_path(world: &WorldCache, start: Vec3, goal: Vec3, max_fall: i32, max_nodes: usize) -> Option<Path>`
- [X] T034 [P] [US1] Port `python/minecraft_bot/physics.py` → `rust/src/physics.rs` (20 Hz tick: gravity, water/lava, slab/ledge math; deterministic per Principle VII)
- [X] T035 [US1] Port `python/minecraft_bot/behaviour/walk_to.py` → `rust/src/behaviour/walk_to.rs`; enforce 5-block anti-cheat cap on Player Position sends (data-model.md validation rules)
- [ ] T036 [P] [US1] Port `python/minecraft_bot/behaviour/hazards.py` → `rust/src/behaviour/hazards.rs` (slab/water/ledge/drop detection + recovery)
- [X] T037 [P] [US1] Port `python/minecraft_bot/inventory_click.py` drop/pickup window-click flow → `rust/src/behaviour/window_click.rs`; wait for `confirm_transaction` per data-model.md
- [X] T038 [US1] Extend `rust/src/connection.rs` with the full tick-loop: keep-alive, observation-side packet handlers updating WorldCache, graceful disconnect on cancel, hooks bus
- [X] T039 [US1] Create `rust/src/bot.rs` — the top-level Bot facade — composing connection, world, walk_to, observation, hooks; mirror `python/minecraft_bot/bot.py` API one-for-one
- [X] T040 [P] [US1] Add Rust-side unit tests in `rust/tests/world_cache.rs` exercising T024–T027
- [X] T041 [P] [US1] Add Rust-side unit tests in `rust/tests/pathfinding.rs` exercising T032–T033 over a fixture 64×64 walkable world
- [X] T042 [P] [US1] Add Rust-side unit tests in `rust/tests/physics.rs` exercising T034 deterministically against the Python physics golden traces from 002

### Tests for User Story 1 (TDD — write FIRST, expect failure pre-T044+)

- [ ] T043 [P] [US1] Write `tests/python/parity/test_api_surface.py` enumerating every public symbol of `minecraft_bot` and asserting matching presence + signature in `minecraft_bot_accel` per `contracts/api-surface.md`
- [ ] T044 [P] [US1] Write `tests/python/parity/test_field_parity.py` introspecting `__dataclass_fields__` of every Python dataclass listed in `data-model.md` parity table and asserting matching `__dict__` / `get_all`-exposed attrs in accel
- [ ] T045 [P] [US1] Write `tests/python/parity/test_us1_substitution.py` (live, mark `pytest.mark.live`) — Python and accel bots connect in sequence to Paper, walk to (10005,200,10005), drop an item, disconnect; assert position parity within 0.5 blocks per quickstart.md
- [X] T046 [P] [US1] Write `tests/python/parity/test_observation_parity.py` asserting `bot_py.observation().to_dict() == bot_acc.observation().to_dict()` after a deterministic packet trace replay

### PyO3 façade — wrap T024–T039 into `python-ext/src/`

- [ ] T047 [P] [US1] Add `python-ext/src/slots.rs` `#[pyclass] PyItemStack` with `get_all` fields per data-model.md
- [ ] T048 [P] [US1] Add `python-ext/src/observation.rs` `#[pyclass] PyVec3`, `PyObservation`; implement `__repr__`, `__eq__`, `to_dict`/`from_dict`
- [ ] T049 [P] [US1] Add `python-ext/src/effects.rs` `#[pyclass] PyStatusEffect`
- [ ] T050 [P] [US1] Add `python-ext/src/entities.rs` `#[pyclass] PyEntity` with metadata-dict access
- [X] T051 [P] [US1] Add `python-ext/src/world/mod.rs` registering `PyWorld`, `PyChunk`, `PyChunkSection`, `PyBlock` per data-model.md and api-surface.md
- [X] T052 [P] [US1] Add `python-ext/src/pathfinding.rs` `#[pyclass] PyPath` (steps, cost, node_count) wrapping Rust path output
- [X] T053 [US1] Add `python-ext/src/connection.rs` `#[pyclass] PyConnection`; expose `offline`, `connect`, `disconnect`, `send`, `state`, `is_connected` as async-aware methods using `pyo3_async_runtimes::tokio::future_into_py`
- [X] T054 [US1] Add `python-ext/src/bot.rs` `#[pyclass] PyBot`; expose `offline`, `connect`, `disconnect`, `tick`, `run`, `walk_to`, `observation`, `use_item`, `drop_held_item`, `send`, `on_packet`, `pre_tick`, `post_tick`, plus the property surface (`world`, `position`, `health`, `food`, `yaw`, `pitch`, `on_ground`, `inventory`, `effects`)
- [ ] T055 [US1] Add `python-ext/src/protocol/mod.rs` registering a submodule tree mirroring `python/minecraft_bot/protocol/v763/packets/{state}/{direction}/*` — each leaf module exposes the packet dataclass type + `encode` / `decode` per api-surface.md
- [ ] T056 [US1] Register T047–T055 modules on the root `#[pymodule]` in `python-ext/src/lib.rs`; rebuild via `maturin develop --release`

### Integration: green parity tests under `--backend accel`

- [ ] T057 [US1] Run `pytest --backend accel tests/python/parity/test_api_surface.py tests/python/parity/test_field_parity.py tests/python/parity/test_observation_parity.py` — all green
- [ ] T058 [US1] Run `pytest --backend accel tests/python/parity/test_us1_substitution.py -m live` against Paper at 172.26.160.1:25565 — green
- [ ] T059 [US1] Run the entire existing unit + replay suite (`pytest --backend accel tests/python/unit tests/python/replay`) — must reach the same pass count as `--backend python`

**Checkpoint**: User Story 1 fully functional. A user can swap imports and run their existing 002-era bot script unchanged against the live server. MVP gate met.

---

## Phase 4: User Story 2 — Cross-platform pre-built wheels (P1)

**Goal**: A pre-built abi3 wheel exists for Linux x86_64, Linux
aarch64, macOS arm64, macOS x86_64, and Windows x86_64. Each wheel
installs in a clean container via `pip install` (no Rust toolchain),
imports cleanly, and passes a smoke test of the Phase 3 parity suite.

**Independent Test**: A GitHub Actions matrix tag build produces 5
wheels; a separate matrix install-and-smoke job downloads each wheel
into a fresh container and runs `tests/python/parity/test_smoke_bringup.py`
plus `test_api_surface.py`. All five green.

- [X] T060 [P] [US2] Create `.github/workflows/wheels.yml` with five jobs: linux-x86_64 (manylinux2014 container, PyO3/maturin-action), linux-aarch64 (cross via `aarch64-unknown-linux-gnu`), macos-arm64 (macos-latest native), macos-x86_64 (macos-latest with `--target x86_64-apple-darwin`), windows-x86_64 (windows-latest native); each uses `maturin build --release --strip --interpreter python3.11` (abi3 single-build)
- [X] T061 [US2] In `wheels.yml`, upload each job's `target/wheels/*.whl` as a build artifact named `wheel-{os}-{arch}`
- [X] T062 [P] [US2] Add a second `wheels.yml` job `smoke-test` (matrix over the 5 platforms) that downloads its artefact, `pip install`s it into a clean Python 3.11 venv, and runs `pytest tests/python/parity/test_smoke_bringup.py tests/python/parity/test_api_surface.py` against `--backend accel`
- [X] T063 [P] [US2] Add a `smoke-test` extra row for Python 3.12 on Linux x86_64 (the only OS where we already have 3.12 in CI containers) to verify abi3 single-wheel coverage of both interpreters
- [X] T064 [US2] Create `.github/workflows/release.yml` triggered on tag push (`v*`); depends-on `wheels.yml`; downloads all 5 artifacts and uploads them to the GitHub release using `gh release upload`
- [ ] T065 [US2] Write `tests/python/parity/test_us2_wheel_smoke.py` — a CI-only smoke that asserts `pip show minecraft_bot_accel` returns and the wheel size is under the 5 MiB budget (R-011); fails the build if the budget is exceeded
- [ ] T066 [US2] Run the workflow manually via `workflow_dispatch` once Phase 3 lands; capture sample wheel sizes and record them in `specs/003-rust-pyo3-bridge/quickstart.md` "wheel sizes" footnote for future regressions

**Checkpoint**: Pre-built wheels exist on the 5 platforms × Python 3.11+3.12; installs are toolchain-free and under 30 seconds on Linux x86_64 (SC-001).

---

## Phase 5: User Story 3 — Behavioural parity with Python reference (P1)

**Goal**: Every existing Python test in `tests/python/unit`,
`tests/python/replay`, and `tests/python/integration`, plus the
cross-check tool, passes byte-for-byte and value-for-value under
both backends.

**Independent Test**: CI runs `pytest --backend python` and
`pytest --backend accel` on the full suite; both report the same
pass count, and `python tools/cross_check.py --backend all` exits
0 with zero discrepancies across the 50 primitive + 36 per-packet
fixtures.

- [X] T067 [P] [US3] Extend `tools/cross_check.py` to accept `--backend {python,rust,accel,all}`; when `all`, run every fixture through all three encoders and assert hash equality
- [ ] T068 [P] [US3] Write `tests/python/parity/test_wirelog_parity.py` — capture a deterministic 30-second packet trace under each backend (mocked clock; offline mode), then diff the resulting JSONL ignoring `ts` field per data-model.md "WireLog format invariance"
- [ ] T069 [P] [US3] Write `tests/python/parity/test_connection_state.py` — drive a 5-second canned login session under each backend and assert state transitions matched event-for-event per data-model.md Connection FSM
- [ ] T070 [P] [US3] Write `tests/python/parity/test_packet_encode_parity.py` — for every packet in `minecraft_bot.protocol.v763.packets`, build a representative instance, encode under both backends, assert byte equality
- [ ] T071 [P] [US3] Write `tests/python/parity/test_walk_to_packet_trace.py` — issue `bot.walk_to(...)` under each backend with a fixed pathfinding seed; capture outbound Player-Position packets via WireLog; assert byte-identical sequences (Principle IV: bots are packet sets)
- [X] T072 [US3] Update `.github/workflows/ci.yml` to run a `parity-matrix` job: matrix `backend = [python, accel]`; runs unit + replay + parity suites; both must pass for the PR to merge
- [ ] T073 [US3] Update `.github/workflows/ci.yml` to add a `live-parity` job (gated on `pull_request_target` to a `live-tests` label) running `pytest --backend accel -m live` against Paper 1.20.1; required for any PR touching `python-ext/`, `rust/`, or `tools/cross_check.py`
- [ ] T074 [US3] Update `.github/workflows/ci.yml` with a `cross-check-all` job invoking `python tools/cross_check.py --backend all`; required-status for any PR touching codec/packet modules
- [ ] T075 [US3] Verify SC-006 (zero cross-check discrepancies) by running T074 once locally; if any fixture mismatches, file a bug and fix on the accel side before merging Phase 5

**Checkpoint**: Behavioural parity gate green; the accel package can be installed alongside any 002-era code path with confidence.

---

## Phase 6: User Story 4 — Native-speed hot paths (P2)

**Goal**: Performance success criteria SC-008…SC-010 are met on
representative microbenchmarks. The accel package is measurably
faster than the Python reference for varint, NBT, chunk decode, and
A* pathfinding.

**Independent Test**: `pytest --benchmark-only -m "not live"
tests/python/perf/test_speedup.py` reports median speedups meeting
the SC-008/009/010 thresholds (≥ 5× / 10× / 10× / 5×).

- [ ] T076 [P] [US4] Add `py.allow_threads(|| { ... })` wrapper around the CPU-bound section of `python-ext/src/world/mod.rs` chunk-decode entry point, plus `python-ext/src/codec/nbt.rs` decode entry, plus `python-ext/src/pathfinding.rs::find_path` entry — per research.md R-005
- [ ] T077 [P] [US4] Write `tests/python/perf/test_speedup_varint.py` using `pytest-benchmark`: parametrise over both backends and assert accel median ≥ 5× python median (SC-008)
- [ ] T078 [P] [US4] Write `tests/python/perf/test_speedup_nbt.py` — same pattern; 1 KiB NBT payload; assert ≥ 10× (SC-009)
- [ ] T079 [P] [US4] Write `tests/python/perf/test_speedup_chunk.py` — fixture set of 100 chunks from `protocol-data/v763/live_captures/`; assert median ≥ 10× (SC-010)
- [ ] T080 [P] [US4] Write `tests/python/perf/test_speedup_pathfinder.py` — 64×64 navigable test world from 002 fixtures; assert median ≥ 5× (SC-011)
- [ ] T081 [US4] Add `.github/workflows/ci.yml` `perf-gate` job running T077–T080 on every PR touching `python-ext/` or `rust/src/{codec,world,pathfinding}/`; soft-fail on first regression (warn), hard-fail on > 10% drop from rolling baseline
- [ ] T082 [US4] Verify SC-012 (chunk-decode CPU drop ≥ 50% during live play) by capturing a 60-second arena session under both backends with `time` / `psutil` instrumentation; record numbers in `specs/003-rust-pyo3-bridge/research.md` under a new "measured speedups" appendix

**Checkpoint**: Hot-path speedups meet the spec's success criteria; CI gates regressions on every PR.

---

## Phase 7: User Story 5 — Physics tick parity at native speed (P3)

**Goal**: 20 Hz physics tick under the accel backend is ≥ 2× faster
than Python (SC-011) and a live arena hazard-course run completes
with no behavioural divergence between backends (FR-019).

**Independent Test**: `tests/python/perf/test_tick_latency.py` shows
accel median ≥ 2× faster; `tests/python/integration/test_hazard_arena.py`
passes under both backends.

- [ ] T083 [P] [US5] Write `tests/python/perf/test_tick_latency.py` parametrising over both backends; load the existing 002 tick golden trace; assert accel median ≥ 2× python median (SC-011)
- [ ] T084 [P] [US5] Write `tests/python/integration/test_hazard_arena_parity.py` (live, mark `pytest.mark.live`) — run the existing hazard-arena test from 002 under both backends sequentially; assert both complete and traverse the same set of safe blocks
- [ ] T085 [US5] Verify SC-013 (60 s normal-play CPU ≥ 25% drop) by re-running the CPU-instrumented arena session from T082 with movement enabled (which exercises the physics tick); record results
- [ ] T086 [US5] Add `tests/python/perf/test_tick_latency.py` and `test_hazard_arena_parity.py` to the CI `perf-gate` job from T081

**Checkpoint**: Physics-tick speedup verified; live arena hazard course confirmed safe under accel.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Release-readiness work that touches multiple stories.

- [ ] T087 [P] Update repo-root `README.md` adding a "Two Implementations" section pointing to `python/` and `python-ext/`, install commands, and the import-substitution recipe from quickstart.md
- [ ] T088 [P] Add `docs/migration_to_accel.md` describing how to migrate a 002-era bot script to the accel backend (the single-import edit + benchmark hint)
- [ ] T089 [P] Update `CLAUDE.md` after-the-fact summary noting 003 is complete (post-implementation hook will land this automatically but final wording deserves a manual review)
- [ ] T090 [P] Run `cargo clippy --workspace --all-targets -- -D warnings`; fix any warnings introduced by the port (Rust-side hygiene)
- [ ] T091 [P] Run `ruff check tests/python` and `black tests/python`; fix style on the new parity + perf test files
- [ ] T092 Bump `python-ext/Cargo.toml` package version from `0.1.0` → `0.2.0` once Phase 7 lands; tag the release; trigger `release.yml`
- [ ] T093 Validate the full `quickstart.md` acceptance checklist (the 8-bullet list at the bottom of that file) before declaring 003 done
- [ ] T094 [P] Update memory at `.claude/projects/.../memory/project_milestone_status.md` setting "003-rust-pyo3-bridge complete"; add a memory entry for the abi3 wheel matrix gotchas (any cross-build quirks discovered in T060)
- [ ] T095 [P] Compress the cross-check tool output of T067 into a one-line CI summary so PR conversations stay readable

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no deps; starts immediately.
- **Phase 2 (Foundational)**: depends on Phase 1; BLOCKS every user-story phase.
- **Phase 3 (US1)**: depends on Phase 2; produces the bulk of the work; gates US2/3 because there must be a non-empty native package to ship/parity-test.
- **Phase 4 (US2 — wheels)**: depends on Phase 3 (something to package); independent of Phase 5/6/7.
- **Phase 5 (US3 — parity)**: depends on Phase 3 (something to compare); independent of Phase 4/6/7 but typically runs alongside Phase 4.
- **Phase 6 (US4 — speedups)**: depends on Phase 3 and Phase 5 (parity must be green before optimisation work is meaningful); independent of Phase 4/7.
- **Phase 7 (US5 — physics)**: depends on Phase 3, 5; can run after or alongside Phase 6.
- **Phase 8 (Polish)**: depends on all user-story phases being complete; finalises the release.

### Within Phase 3 (US1)

- Rust port tasks T024–T039 are mostly file-disjoint; many run in parallel.
- Rust unit tests T040–T042 run after their corresponding port tasks land.
- Parity tests T043–T046 are written BEFORE the corresponding PyO3 wrappers (TDD).
- PyO3 façade tasks T047–T055 depend on the matching Rust port; they're file-disjoint among each other.
- T056 (register all submodules) depends on T047–T055 being complete.
- T057–T059 (green tests) depend on T056.

### Within Phase 4 (US2)

- T060–T065 are largely independent; T064 (release.yml) depends on T060 (wheels.yml).

### Within Phase 5 (US3)

- T067 (cross-check tool) and T068–T071 (parity tests) are file-disjoint and run in parallel.
- T072–T074 (CI wiring) depend on the tests existing.

### Parallel Opportunities

- **Phase 1**: T006, T007, T008, T010 all [P].
- **Phase 2**: T014, T015, T017, T018, T019, T022 all [P]; T020 (lib.rs registration) is the serialisation point.
- **Phase 3 Rust port**: T024, T025, T027, T028, T029, T030, T032, T034, T036, T037, T040, T041, T042 all [P] (different files).
- **Phase 3 PyO3 façade**: T047, T048, T049, T050, T051, T052 all [P]; T053, T054, T055 depend on their Rust counterparts.
- **Phase 4**: T060, T062, T063, T065 all [P].
- **Phase 5**: T067, T068, T069, T070, T071 all [P].
- **Phase 6**: T076, T077, T078, T079, T080 all [P].
- **Phase 7**: T083, T084 [P].
- **Phase 8**: T087, T088, T089, T090, T091, T094, T095 all [P].

---

## Parallel Example: Phase 3 Rust port (US1)

```bash
# Launch port tasks T024–T030 in parallel — each touches a distinct file:
Task: "Port world/chunk.py → rust/src/world/chunk.rs (T024)"
Task: "Port world/decode_chunk.py → rust/src/world/decode_chunk.rs (T025)"
Task: "Port world/block_table.py → rust/src/world/block_table.rs (T027)"
Task: "Port slots.py → rust/src/slots.rs (T028)"
Task: "Port entities/*.py → rust/src/entities/ (T029)"
Task: "Port status_effects.py → rust/src/effects.rs (T030)"

# Once those land, run T032/T034/T036/T037 in parallel:
Task: "Port pathfinding walkable graph → rust/src/pathfinding/walkable.rs (T032)"
Task: "Port physics.py → rust/src/physics.rs (T034)"
Task: "Port behaviour/hazards.py → rust/src/behaviour/hazards.rs (T036)"
Task: "Port inventory_click.py → rust/src/behaviour/window_click.rs (T037)"
```

## Parallel Example: Phase 5 Parity (US3)

```bash
# All five parity tests are file-disjoint:
Task: "Extend tools/cross_check.py for third encoder (T067)"
Task: "WireLog parity test → tests/python/parity/test_wirelog_parity.py (T068)"
Task: "Connection-state parity → tests/python/parity/test_connection_state.py (T069)"
Task: "Packet encode parity → tests/python/parity/test_packet_encode_parity.py (T070)"
Task: "walk_to packet trace parity → tests/python/parity/test_walk_to_packet_trace.py (T071)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) — bring up `python-ext/` + maturin + backend fixture (~T001–T011).
2. Phase 2 (Foundational) — errors, async runtime, version attributes, codec/framer/wire_log wrappers (~T012–T023).
3. Phase 3 (US1) — Rust port of full 002 + PyO3 façade + parity tests (~T024–T059).
4. **STOP and VALIDATE**: end-to-end live-server substitution test green (T058) → US1 MVP shipped.

Branch can be merged at this point — users get a native-backed Bot with no wheels (developer-only `maturin develop` build); parity tests gate every PR.

### Incremental Delivery After MVP

1. Phase 4 (US2 — wheels) — adds pre-built distribution. Now users without a Rust toolchain can install.
2. Phase 5 (US3 — parity sweep) — extends the gate from "US1 works" to "every existing test works on both backends" + cross-check.
3. Phase 6 (US4 — speedups) — proves and gates the performance claims.
4. Phase 7 (US5 — physics) — final speedup category.
5. Phase 8 (Polish) — docs, release tag, memory update.

Each phase 4–7 can be its own PR; each can be reverted independently if it regresses.

### Parallel Team Strategy

With two developers:

- Dev A: Phase 3 Rust port (T024–T042) — heavy code.
- Dev B: Phase 3 PyO3 façade scaffolding (T047–T055) once T012–T020 land, then T043–T046 parity tests.
- After Phase 3 merge: Dev A starts Phase 4 (wheels), Dev B starts Phase 5 (parity sweep).
- Phase 6 + 7 split across the two.

With one developer: walk phases in order, respect the parallel-opportunities markers within each phase to minimise context switching.

---

## Notes

- The Constitution VI invariant (`python/pyproject.toml dependencies = []`) is preserved throughout — at no point does the Python reference depend on the native package. Phase 3 work touches `rust/` and `python-ext/`; `python/minecraft_bot/` stays unedited except for the optional test-helper migration in T010.
- Cross-language parity (Principle I + R-009 WireLog invariance + cross-check tool R-006) is the primary correctness gate. Two failure paths to watch: byte divergence in codec/packet encode, and observable divergence in physics/walk_to. Both have dedicated tests (T070/T071 byte parity; T046/T084 behavioural parity).
- Live-server tests (Constitution V) cover both backends in T058, T073, T084 — non-negotiable for merging anything in `rust/src/` or `python-ext/src/connection.rs`.
- `pyo3-async-runtimes` registers one tokio runtime per process. T014 owns the OnceLock guard. Test infra (T009) must not create a second runtime; ScheduledWakeup-style sleeps inside tests already cooperate with the host loop.
- Wheel-size and import-time budgets (R-011) are soft (T065 tracks, doesn't block) — keep an eye on them as the Rust crate grows.
- After each phase, the after-hook auto-commit fires; review the diff before pushing.
