# Implementation Plan: Rust + PyO3 framework port

**Branch**: `003-rust-pyo3-bridge` | **Date**: 2026-05-12 | **Spec**: [`spec.md`](spec.md)
**Input**: Feature specification from `/specs/003-rust-pyo3-bridge/spec.md`

## Summary

Build a complete alternative implementation of the `minecraft_bot`
public API in Rust and expose it to Python via PyO3 as the standalone
package `minecraft_bot_accel`. The Rust standalone crate grows from its
current 001 scope (codec, framer, packets, basic Connection) to cover
every 002 bot-API capability: World/Chunk cache, observation snapshot,
walk_to + path planner, hazard handling, 20 Hz physics tick, full
async Connection lifecycle (login → play → keep-alive → graceful
disconnect), and drop/pickup window-click flow. A thin PyO3 façade
then mirrors the entire Python public surface — Bot, World, Connection,
codec/framer/protocol modules — with structurally identical native
types and `pyo3-async-runtimes`-bridged awaitables. Distribution is via
pre-built abi3 wheels for Linux x86_64/aarch64, macOS arm64/x86_64,
and Windows x86_64, built by `maturin` in a GitHub Actions matrix and
attached to GitHub releases.

The Python reference stays untouched and remains the authoritative
behavioural spec. Users switch implementations by changing the
top-level import only.

## Technical Context

**Language/Version**: Python 3.11+ (target 3.11 & 3.12 via abi3),
Rust stable edition 2021 (msrv 1.75).
**Primary Dependencies**:
- Rust crate already on: `tokio`, `bytes`, `flate2`, `thiserror`
  (Constitution VI minimum).
- Added for 003: `pyo3 = { version = "0.22", features = ["extension-module", "abi3-py311"] }`,
  `pyo3-async-runtimes = { version = "0.22", features = ["tokio-runtime"] }`.
- Build tool: `maturin >= 1.5` (dev-time only).

**Storage**: N/A (no persisted state; WireLog continues to write
JSONL via the existing file API).

**Testing**:
- `cargo test` for Rust-side units + integration (continues from 001).
- `pytest` for Python-side unit + replay + live, **parametrised** over
  the two implementations (`minecraft_bot` and `minecraft_bot_accel`)
  so the same test code runs against both backends.
- Existing cross-check tool extended to accept a third encoder
  (`minecraft_bot_accel`).
- `pytest-benchmark` comparing the two backends head-to-head.

**Target Platform**:
- **Build / wheel build**: Linux x86_64, Linux aarch64 (cross from
  ubuntu-latest), macOS arm64, macOS x86_64, Windows x86_64.
- **Runtime**: any platform with Python 3.11+ that has a matching
  pre-built wheel.
- **Test**: live integration against Paper 1.20.1 at
  `172.26.160.1:25565` (offline-mode), same as 001/002.

**Project Type**: monorepo with three artefacts —
1. `python/` — existing Python reference, **untouched**.
2. `rust/` — existing Rust crate, **expanded** to cover full bot-API.
3. `python-ext/` — new directory hosting the PyO3 façade
   (`minecraft_bot_accel`) built by maturin.

**Performance Goals** (from spec SC-008…SC-013):
- VarInt encode/decode ≥ 5× faster than Python.
- NBT decode (1 KiB payload) ≥ 10× faster.
- Chunk decode ≥ 10× faster.
- A* on 64×64 ≥ 5× faster.
- Physics tick ≥ 2× faster.
- 60 s normal-play CPU ≥ 25% lower.

**Constraints**:
- abi3 stable Python ABI — single wheel per (os, arch) covers Python
  3.11 and 3.12.
- Linux wheels target manylinux2014 (glibc 2.17+).
- GIL released for all CPU-bound sections > 10 µs.
- Public-type contract: separate-but-structurally-identical (no
  cross-package imports).
- Behavioural parity is the primary correctness gate — no
  Rust-only features in this milestone.

**Scale/Scope**:
- Wheel count: 5 platforms × 1 ABI = 5 wheels per release.
- Rust source growth: ~+8k LOC (porting 002 bot-API surface).
- PyO3 façade: ~+1.5k LOC of thin wrappers.
- Test parametrisation: every existing test (~990 unit + ~30 live +
  ~36 cross-check) runs against both backends → effective test
  count ≈ 2×.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1
design.*

| # | Principle | Verdict | Notes |
|---|-----------|---------|-------|
| I | Python is source of truth | **PASS** | Python reference stays untouched and remains the authoritative spec. Rust/PyO3 chases Python parity; cross-check tool is mandatory before merging any accel-side codec or packet change. |
| II | One packet, one file; versions in folders | **PASS** | Rust already follows this layout for v763 packets. No new packet files added in 003 (we wrap existing ones). |
| III | PyTorch-style composable API | **PASS** | `minecraft_bot_accel.Bot` mirrors `minecraft_bot.Bot` exactly — `bot.world`, `bot.movement`, observation/hook surface. No new idiom introduced. |
| IV | Bots are packet sets, not entities | **PASS** | Native Bot translates every high-level action into the same packets the Python reference sends; cross-check fixtures enforce this byte-for-byte. |
| V | Live-server integration testing | **PASS** | Live test suite runs against both backends. CI matrix `with_accel=true \| false`. Cannot merge accel without green live. |
| VI | Zero runtime deps in core | **PASS** | Python reference still has `dependencies = []`. `minecraft_bot_accel` is a separate distributable; users opt in. Rust core adds `pyo3` + `pyo3-async-runtimes` — these are build/extension deps, not core protocol deps, and they live behind the new `python-ext` crate (see Project Structure). The codec/protocol crate stays unchanged. |
| VII | Observability and determinism | **PASS** | WireLog format invariant: both backends MUST emit identical JSONL bytes for the same packet stream (covered by FR-013 cross-check). Physics tick must be deterministic under both backends; replay test covers this. |

**Gate result (pre-design)**: **PASS** — proceeding to Phase 0.

**Outstanding clarifications** (resolved in spec.md `## Clarifications`):
- Architecture: full alternative implementation, not overlay
  (Session 2026-05-12 Q1).
- Scope: full Rust port of 002 + PyO3 wrap (Q2).
- Async bridge: `pyo3-async-runtimes` (Q3).
- Type contract: separate, structurally identical (Q4).

### Phase 1 post-design re-check (2026-05-12)

After producing `research.md`, `data-model.md`,
`contracts/api-surface.md`, and `quickstart.md`, every principle was
re-evaluated against the concrete design:

| # | Principle | Re-check | Evidence in artefacts |
|---|-----------|---------|-----------------------|
| I | Python source-of-truth | **PASS** | data-model.md parity table makes Python the spec; cross-check tool (R-006) gates every codec/packet change. |
| II | One packet, one file | **PASS** | api-surface.md preserves per-packet module layout in accel namespace. |
| III | PyTorch-style API | **PASS** | api-surface.md keeps `bot.world`, `bot.movement`, and the hooks API verbatim. |
| IV | Bots are packet sets | **PASS** | data-model.md validation rules carry the 5-block anti-cheat cap and confirm_transaction wait into the Rust port. |
| V | Live integration testing | **PASS** | quickstart.md mandates `pytest --backend accel -m live`; CI matrix in plan.md adds an accel-live job. |
| VI | Zero deps in core | **PASS** | `python/pyproject.toml` `dependencies = []` invariant preserved; accel ships as a separate distributable; standalone Rust crate stays PyO3-free (PyO3 lives only in `python-ext/`). |
| VII | Observability + determinism | **PASS** | R-009 mandates byte-identical WireLog JSONL across backends; data-model.md adds a WireLog roundtrip diff test. |

**Gate result (post-design)**: **PASS** — no Constitution-Check
violations introduced by Phase 1 design. Ready for `/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/003-rust-pyo3-bridge/
├── plan.md              # This file
├── spec.md              # Feature spec + clarifications
├── research.md          # Phase 0: technical decisions
├── data-model.md        # Phase 1: native-side data shapes
├── quickstart.md        # Phase 1: how to build, install, run, switch
├── contracts/
│   └── api-surface.md   # Public symbol parity between mb and mb_accel
├── checklists/
│   └── requirements.md  # Created in /speckit-specify
└── tasks.md             # /speckit-tasks output (not created here)
```

### Source Code (repository root)

```text
python/                                # UNTOUCHED — Python reference impl
└── minecraft_bot/
    ├── bot.py
    ├── connection.py
    ├── codec/, world/, behaviour/, protocol/v763/, …

rust/                                  # EXPANDED — standalone crate
└── src/
    ├── codec/                         # existing (001)
    ├── framer.rs                      # existing (001)
    ├── protocol/v763/                 # existing (001) — all 176 packets
    ├── connection.rs                  # existing (001) — extended for 003
    ├── wire_log.rs                    # existing (001)
    ├── world/                         # NEW (003) — Chunk cache, block lookup,
    │   ├── cache.rs                   #   parity with python/minecraft_bot/world/
    │   ├── chunk.rs
    │   └── decode_chunk.rs
    ├── observation.rs                 # NEW (003) — Observation snapshot
    ├── pathfinding/                   # NEW (003) — A* + walkable-graph builder
    │   ├── astar.rs
    │   └── walkable.rs
    ├── physics.rs                     # NEW (003) — 20 Hz tick
    ├── behaviour/                     # NEW (003) — walk_to, hazards, drop/pickup
    │   ├── walk_to.rs
    │   ├── hazards.rs
    │   └── window_click.rs
    └── bot.rs                         # NEW (003) — top-level Bot facade

python-ext/                            # NEW (003) — PyO3 façade crate
├── Cargo.toml                         #   produces cdylib for minecraft_bot_accel
├── pyproject.toml                     #   maturin build backend
├── src/
│   ├── lib.rs                         # #[pymodule] root
│   ├── bot.rs                         # #[pyclass] Bot
│   ├── connection.rs                  # #[pyclass] Connection + async bridge
│   ├── world.rs                       # #[pyclass] World + Chunk + Block
│   ├── observation.rs                 # #[pyclass] Observation, Vec3, etc.
│   ├── codec.rs                       # #[pyclass] Reader/Writer + pyfn primitives
│   ├── framer.rs                      # #[pyclass] Framer
│   ├── protocol/                      # #[pymodule] mirror of v763 packets
│   └── wire_log.rs                    # #[pyclass] WireLog
└── minecraft_bot_accel/               # Python-import layer (re-exports from native)
    └── __init__.py                    #   `from .minecraft_bot_accel import *`

tests/
├── python/
│   ├── unit/                          # existing — parametrised over both backends
│   ├── integration/                   # existing — live tests param'd
│   ├── parity/                        # NEW — head-to-head behavioural diff
│   │   └── test_backend_parity.py
│   └── perf/                          # NEW — pytest-benchmark backend comparison
│       └── test_speedup.py
└── conftest.py                        # NEW — backend fixture; injects either
                                       #   `minecraft_bot` or `minecraft_bot_accel`
                                       #   based on `--backend` CLI option.

tools/
└── cross_check.py                     # existing — EXTENDED to accept a third
                                       #   encoder (`accel`) alongside py + rust

.github/workflows/
├── ci.yml                             # existing — runs unit/replay against both
├── wheels.yml                         # NEW — maturin matrix build across platforms
└── release.yml                        # NEW — tag → wheels.yml → upload to release
```

**Structure Decision**:
- Three top-level crates / package roots:
  1. `python/minecraft_bot/` — Python reference, no changes.
  2. `rust/` (crate `minecraft_bot`) — standalone Rust framework; grows
     to cover the full 002 bot-API.
  3. `python-ext/` (crate `minecraft_bot_accel`, separate
     `Cargo.toml`) — PyO3 façade; depends on the `minecraft_bot` Rust
     crate as a path-dependency; produces a cdylib that maturin
     packages into the wheel.
- We add a **separate** crate for the PyO3 façade rather than putting
  PyO3 features behind a cargo feature flag in the existing `minecraft_bot`
  crate. Rationale:
  - Keeps the standalone Rust crate free of PyO3 compile-time
    constraints (`#[pyclass]` requires Send + 'static + no lifetimes
    that escape).
  - Constitution VI: Python reference's zero-dep posture is mirrored
    on the Rust side — codec/protocol crate carries `tokio`/`bytes`
    only.
  - Lets users link the Rust crate from a non-Python program (CLI,
    custom service) without pulling Python.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New crate `python-ext/` distinct from `rust/` | Separation of concerns: keep `rust/` PyO3-free so non-Python consumers can link it; keep `python-ext/` focused on FFI surface. | Single crate with `pyo3` behind a feature flag — rejected because cdylib output and `#[pyclass]` impl blocks bleed into normal `cargo build` flow and add binary size; also harder to keep stable-ABI guarantee local to one crate. |
| Cross-package public-type duplication (Observation, Vec3, Block, …) in both `mb` and `mb_accel` | Constitution VI invariant: `minecraft_bot` MUST NOT depend on `minecraft_bot_accel`. Re-using types either direction breaks this. | Single shared type package (`minecraft_bot_types`) — rejected because it imposes a third pip-installable dependency on the **Python reference**, breaking Constitution VI's zero-dep stance. The structural-identity contract + parity tests give us interop without coupling. |
| Two CI matrix runs of the Python test suite | FR-017 mandates both backends pass; we cannot install both into the same env without import ambiguity. | Single run with import-substitution monkeypatch — rejected because it hides backend-specific bugs (different exception classes, different async cooperativity edges); explicit two-pass run finds them. |
