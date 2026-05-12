# Feature Specification: Rust + PyO3 framework port

**Feature Branch**: `003-rust-pyo3-bridge`
**Created**: 2026-05-12
**Status**: Draft
**Input**: User description: "Rust+PyO3 bridge — Python-facade поверх ПОЛНОГО Rust-фреймворка (001-protocol-foundation + расширения), а не overlay-ускоритель отдельных функций. Цепочка: Python (reference + dev-loop) → Rust standalone (proven, fast, full framework) → PyO3 wrapper (Python API, native speed). Цель — иметь альтернативную, byte-compatible реализацию `minecraft_bot.Bot` с нативной скоростью."

## Clarifications

### Session 2026-05-12

- Q: FR-005 (per-module dispatch) vs Edge Case (per-call fallback) противоречат — какая семантика правильная?
  → A: Ни та, ни другая. Архитектура — **альтернативная полная реализация**, а не overlay-ускоритель. Rust crate целиком обёрнут в PyO3 и поставляется как самостоятельный пакет `minecraft_bot_accel` с тем же публичным API, что и `minecraft_bot` (Bot, World, Connection, …). Пользователь выбирает реализацию импортом (`import minecraft_bot` vs `import minecraft_bot_accel`); Python core не содержит ни одной accel-зависимой ветки.
- Q: Что входит в scope 003 — обёртка только готовых частей Rust crate (001) или полный port 002 bot-API + обёртка?
  → A: **Full port + PyO3 wrap**. Милстоун включает (a) Rust-port всего 002 bot-API (World cache, walk_to + path planner, observation, физика 20 Hz, async Connection lifecycle с tick-loop и hazard handling) **в** стандалон-crate; (b) PyO3-façade поверх получившегося полного crate. Оба слоя — часть 003.
- Q: Как Python-сторона видит async-вызовы (Bot.connect/tick/walk_to)? Rust использует tokio; Python ждёт asyncio-cooperative awaitable.
  → A: **pyo3-async-runtimes** (бывший pyo3-asyncio). Каждый Rust-async-метод возвращает Python-coroutine, интегрированный с host asyncio-loop; `await bot.connect()` работает прозрачно. Out of scope "pyo3-asyncio для Connection" из исходного описания **снимается** — async-bridge через pyo3-async-runtimes теперь обязателен.
- Q: Публичные типы (Observation, Vec3, Block, ItemStack) — те же dataclassы из `minecraft_bot` или отдельные `#[pyclass]`?
  → A: **Separate, structurally identical**. `accel` экспонирует свои собственные типы с теми же именами полей и сигнатурами методов. Никаких импортов между пакетами. `isinstance(o, mb.Observation)` ↔ `isinstance(o, mb_accel.Observation)` дают False между пакетами; parity-тесты сравнивают по содержимому, не по identity. Сохраняет FR-004 invariant и развязывает release-cycle двух пакетов.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Native-backed Bot, same public API (Priority: P1) 🎯 MVP

A developer who knows the `minecraft_bot` API can switch to the
native-backed implementation by changing exactly one line — the
top-level import — and observe identical behaviour at higher speed.
No bot-code refactor. No new vocabulary.

**Why this priority**: This is the entire value proposition. If a
developer cannot drop in the native package as a substitute and
have their existing code work unchanged, the milestone has missed
its point. Everything else in this spec assumes API-substitutability
holds.

**Independent Test**: Take an existing bot script that uses
`from minecraft_bot import Bot`. Rewrite the import to
`from minecraft_bot_accel import Bot`. Re-run the script against the
live test server. Verify identical observable behaviour
(connect-to-spawn, walk-to-arena, drop-item, exit) and a faster
end-to-end runtime.

**Acceptance Scenarios**:

1. **Given** a working bot script importing from `minecraft_bot`,
   **When** the developer rewrites only the top-level import to
   `minecraft_bot_accel`,
   **Then** the script connects, walks, and exits with no
   user-code changes and no observable behavioural difference.
2. **Given** a developer comparing the two implementations,
   **When** they list `dir(minecraft_bot)` and
   `dir(minecraft_bot_accel)`,
   **Then** every public symbol exposed by `minecraft_bot` exists
   in `minecraft_bot_accel` with a compatible signature.
3. **Given** the existing public bot-API tests (`bot.observation`,
   `bot.walk_to`, `bot.world.find_blocks_nearby`, `bot.use_item`),
   **When** rerun against `minecraft_bot_accel`,
   **Then** every test passes with the same results.

---

### User Story 2 — Cross-platform pre-built wheels (Priority: P1)

A developer can install the native-backed implementation on Linux
x86_64, Linux aarch64, macOS arm64, macOS x86_64, or Windows x86_64
using `pip install` from a published artefact — without needing a
Rust toolchain on their machine.

**Why this priority**: Without distribution-friendly artefacts the
native implementation is useless to anyone who isn't already a Rust
programmer. We must ship binaries for the platforms users actually
run.

**Independent Test**: From a clean container of each supported
platform, run `pip install <wheel-url-or-path>` and confirm:
1. Install succeeds without invoking a compiler.
2. `python -c "import minecraft_bot_accel"` succeeds.
3. The acceptance test suite passes against the installed package.

**Acceptance Scenarios**:

1. **Given** a vanilla Linux x86_64 container with only Python and
   pip installed (no Rust toolchain, no C compiler),
   **When** the developer runs `pip install minecraft_bot_accel-*.whl`,
   **Then** the install succeeds in under 30 seconds and the package
   imports cleanly.
2. **Given** an Apple silicon Mac with Python 3.12,
   **When** the developer runs `pip install minecraft_bot_accel-*.whl`,
   **Then** the install picks the arm64 wheel and import succeeds.
3. **Given** a Python 3.11 environment AND a Python 3.12 environment,
   **When** the developer installs the same wheel artefact in each
   (single ABI),
   **Then** both versions accept the install and the test suite
   passes in both.

---

### User Story 3 — Behavioural parity with Python reference (Priority: P1)

For every public API call, the native-backed implementation returns
the same observable result (return value, raised errors,
side-effects on shared state) as the Python reference. The Python
implementation remains the authoritative spec for behaviour; the
native implementation is held to its results.

**Why this priority**: Without parity, the native package silently
breaks user bots. Compatibility is the whole point of going through
PyO3 instead of asking users to learn a new API. Even one diverging
edge case turns a clean substitution into a subtle bug source.

**Independent Test**: Run the entire existing Python test suite
twice: once via `minecraft_bot`, once via `minecraft_bot_accel`
(through an import-shim or pytest plugin). Both runs must report
the same pass result on every test.

**Acceptance Scenarios**:

1. **Given** the Python ↔ Rust cross-check fixture set (50
   primitive fixtures + 36 per-packet golden bytes),
   **When** the developer runs the cross-check tool with
   `minecraft_bot_accel` as a third encoder,
   **Then** all three encoders produce byte-identical output across
   every fixture.
2. **Given** the existing unit + replay test suite (~990 tests),
   **When** the test session is parametrised over both
   implementations,
   **Then** the native-backed run reports exactly the same pass
   count and the same per-test results as the Python run — zero
   new failures, zero behavioural divergence.
3. **Given** the live-server integration tests (US1–US7 + hazard
   arena + drop/pickup),
   **When** run against `minecraft_bot_accel`,
   **Then** every previously-green test stays green; no anti-cheat
   warnings, no protocol decode errors, no behavioural divergence.

---

### User Story 4 — Native-speed hot paths (Priority: P2)

Operations that dominate CPU time in Python — chunk decode, A*
pathfinding, NBT decode, varint stream — run at native speed when
the bot is using `minecraft_bot_accel`, because they execute in
Rust without any Python dispatch overhead in the inner loop.

**Why this priority**: This is where the user feels the upgrade.
A native-backed bot should not just match the Python reference; it
should be measurably faster in the operations that limit Python
bots today.

**Independent Test**: Run microbenchmarks for each hot path
(varint, NBT, chunk decode, A*, physics tick) twice — once via
`minecraft_bot` and once via `minecraft_bot_accel`. Native runs
should be faster by the success-criteria margins.

**Acceptance Scenarios**:

1. **Given** a fixture set of 100 chunks captured from the live
   server,
   **When** decoded via `minecraft_bot_accel.world.decode_chunk(...)`,
   **Then** median wall-clock time per chunk is ≥ 10× faster than
   the Python reference.
2. **Given** a 64×64 navigable test world,
   **When** the bot plans paths between 100 random start/goal pairs
   via `minecraft_bot_accel`,
   **Then** median pathfinder runtime is ≥ 5× faster than Python.
3. **Given** a live bot using `minecraft_bot_accel`,
   **When** it walks through chunks streamed during normal play,
   **Then** chunk-decode CPU time drops by ≥ 50% compared to the
   Python reference.

---

### User Story 5 — Physics tick parity at native speed (Priority: P3)

The 20-Hz physics tick — called every 50 ms while moving — runs at
native speed under `minecraft_bot_accel`, freeing CPU for caller
workloads (LLM inference, RL training, running multiple bots in
one process).

**Why this priority**: Physics tick is already fast in pure Python
(< 1 ms median) but it runs constantly. Halving its cost frees real
budget. Not blocking — most users won't notice until they run
several bots in one process.

**Independent Test**: Run the existing physics-tick benchmark
against both implementations; verify the native path is ≥ 2×
faster and the hazard course completes correctly.

**Acceptance Scenarios**:

1. **Given** the existing physics-tick benchmark,
   **When** run against `minecraft_bot_accel`,
   **Then** median tick latency is ≥ 2× faster than Python.
2. **Given** a bot in active movement (walk_to in progress)
   running under `minecraft_bot_accel`,
   **When** it traverses the test arena's hazard course
   (slab/water/ledge/drop),
   **Then** the run completes successfully with no behavioural
   divergence from the Python reference.

---

### Edge Cases

- **Native package not installed**: A user importing
  `minecraft_bot` (the Python reference) sees no change — the
  Python implementation does not import or reference
  `minecraft_bot_accel`. A user explicitly importing
  `minecraft_bot_accel` gets a normal `ImportError` if the wheel
  is absent; this is a hard error, not a fallback.
- **Wheel installed for the wrong Python version**: Pip is
  responsible for selecting the right wheel. A manually mismatched
  wheel will fail at import with a clear error; out of scope to
  handle gracefully.
- **Multiple bots in one process**: Both implementations MUST be
  thread- and asyncio-safe for multiple concurrent `Bot` instances
  within a single Python process.
- **Mixing implementations in one process**: A developer who
  imports both `minecraft_bot` and `minecraft_bot_accel` in the
  same process MUST be able to run instances of each side by side
  without one corrupting the other's state. (Two independent
  module trees with no shared mutable state.)
- **Malformed wire input on native side**: The native
  implementation MUST raise the framework's protocol-error
  exception types (matching the Python reference) — not native
  panics, not generic `RuntimeError`.
- **Mid-run upgrade**: If the user upgrades the native package
  while a Python process is running, the running process keeps
  using the originally-loaded version. Standard Python
  import-time semantics; no hot-reload contract.
- **Async-bridge backpressure**: The native `Connection` runs an
  internal async runtime (separate from Python's asyncio). Awaits
  on the Python side MUST cooperate with the host event loop, not
  block it. Backpressure on the Rust side MUST propagate into
  Python-visible awaitables.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The native package MUST be installable as a
  pre-built binary wheel — no Rust toolchain or C compiler
  required on the user's machine.
- **FR-002**: The native package MUST expose the same public
  surface as `minecraft_bot` (Bot, Connection, World, Codec,
  Framer, Protocol packet modules, WireLog) — every symbol a user
  imports from `minecraft_bot` MUST exist in `minecraft_bot_accel`
  with a compatible signature.
- **FR-003**: For every public call, the native implementation
  MUST return a result observationally identical to the Python
  reference: same return value, same exception type, same
  exception message within reason.
- **FR-004**: The Python reference (`minecraft_bot`) MUST NOT
  depend on, import, or reference `minecraft_bot_accel` in any
  way. It continues to work with zero runtime dependencies.
- **FR-005**: Selection between implementations MUST be
  controlled solely by the user's import (`minecraft_bot` vs
  `minecraft_bot_accel`). No environment variables, no
  configuration flags, no per-call dispatch in either package.
- **FR-006**: The native package MUST be released as a single
  binary wheel per platform that covers every supported Python
  version (stable ABI) — one wheel per (OS, arch) pair, not per
  (OS, arch, py-minor).
- **FR-007**: The native package MUST be distributable for Linux
  x86_64, Linux aarch64, macOS arm64, macOS x86_64, and Windows
  x86_64.
- **FR-008**: Native-side primitives (varint, varlong, NBT codec)
  MUST be byte-identical with the Python reference on every
  existing primitive fixture.
- **FR-009**: Native-side per-packet encoders MUST be
  byte-identical with the Python reference on every existing
  per-packet golden fixture.
- **FR-010**: The native package MUST be thread-safe — multiple
  callers from different OS threads MUST be able to invoke any
  public function concurrently without data corruption.
- **FR-011**: The native package MUST be asyncio-cooperative — a
  Python program that does `bot = mb_accel.Bot.offline(...)`;
  `await bot.connect()`; `await bot.tick()` MUST integrate with
  the caller's `asyncio` event loop the same way the Python
  reference does (yielding on I/O, not blocking the loop).
- **FR-012**: Long-running CPU-bound operations in the native
  package (chunk decode, pathfinding, NBT decode of large
  payloads) MUST release the Python global lock during the
  CPU-bound section, so other Python threads can make progress.
- **FR-013**: Cross-check tooling MUST be extended to support a
  third encoder (the native package) alongside Python and the
  standalone Rust crate, and the parity guarantee MUST hold on
  all existing fixtures.
- **FR-014**: The native package MUST raise the framework's
  protocol-error types (`DecodeError`, `OversizedVarInt`, etc.)
  on malformed input — not native panics, not generic
  `RuntimeError`.
- **FR-015**: The native package MUST be safe to load multiple
  times in the same process, multiple times across processes,
  and inside a `fork`/`spawn` child without corruption.
- **FR-016**: The native package MUST expose a programmatic way
  to query its identity (e.g., a `__version__` or
  `implementation` attribute) so callers and tests can confirm
  which implementation is active.
- **FR-017**: The continuous-integration pipeline MUST run the
  Python test suite twice — once via the Python reference, once
  via the native package — and require both to pass.
- **FR-018**: The continuous-integration pipeline MUST build a
  release artefact for every supported platform and attach it to
  a GitHub release on tag pushes.
- **FR-019**: Live-server integration tests MUST run against the
  native package and reach the same pass result as against the
  Python reference (no anti-cheat warnings, no decode errors, no
  behavioural divergence).
- **FR-020**: The wheel build process MUST be runnable locally by
  a developer with the Rust toolchain installed (`maturin build`
  or equivalent), producing a working wheel that passes the same
  test suite the CI artefacts do.
- **FR-021**: The standalone Rust crate MUST grow to cover every
  capability of the 002 Python bot-API: World/Chunk cache and
  block lookup, observation snapshot construction, walk_to with
  the bot-side path planner, hazard handling (slab/water/ledge/
  drop), the 20 Hz physics tick, async Connection lifecycle
  (login → play → keep-alive → graceful disconnect), and the
  drop/pickup window-click flow. The Rust crate is the source of
  truth for native-side behaviour; PyO3 binds onto it without
  reimplementing logic in glue code.
- **FR-022**: Every piece of native-side state owned by the
  Rust crate MUST be reachable from Python through the PyO3
  façade in a way that preserves the Python reference's public
  semantics (e.g., the World cache exposed via the same
  `bot.world.get_block`, `bot.world.find_blocks_nearby`,
  `bot.observation()` surface).
- **FR-023**: Public data types (`Observation`, `Vec3`, `Block`,
  `ItemStack`, …) MUST be exposed as native-side classes in
  `minecraft_bot_accel` with field names, field types, and method
  signatures identical to the Python reference's dataclasses.
  The two packages MUST NOT import each other's types; cross-type
  `isinstance` checks are not required to succeed. Parity tests
  compare by field content, not by identity.

### Key Entities

- **Python reference implementation** — `minecraft_bot` package,
  authoritative spec for behaviour, dependency-free, never imports
  the native package.
- **Standalone Rust crate** — the `rust/` crate that produces a
  cdylib; the source of truth for native-side logic. Already
  exists from 001 (codec, framer, all 176 packets for protocol
  763, Connection scaffolding, WireLog) and grows substantially
  during this milestone to cover the entire 002 Bot API surface
  (World cache, walk_to, observation, hazards, physics tick,
  Connection lifecycle, drop/pickup).
- **Native-backed implementation** — `minecraft_bot_accel`
  package, a thin PyO3 façade exposing the same public surface as
  `minecraft_bot`, delegating every call into the Rust crate.
- **Async bridge** — the layer that lets a Python `await` cooperate
  with the Rust async runtime: Python-visible awaitables that
  resume the host event loop instead of blocking it.
- **Cross-check fixture** — a triple `(input, expected-bytes,
  expected-decode)` used to verify that all three implementations
  agree byte-for-byte and value-for-value.
- **Compatibility suite** — the existing Python test suite, run
  unmodified against each implementation via parametrisation; the
  primary parity gate.
- **Benchmark suite** — a `pytest-benchmark` test set comparing
  hot-path operations between the two implementations; verifies
  speed-up claims and catches regressions on every CI run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can install the native package on Linux
  x86_64 in under 30 seconds end-to-end (`pip install`), with no
  compiler on the system.
- **SC-002**: A pre-built artefact exists and passes its smoke
  test on each of: Linux x86_64, Linux aarch64, macOS arm64,
  macOS x86_64, Windows x86_64.
- **SC-003**: A single artefact per platform covers Python 3.11
  and 3.12 — no separate wheel per minor version.
- **SC-004**: The full Python unit + replay test suite (≥ 990
  tests as of 002 Phase 10) reports the same pass count when run
  against the native package as against the Python reference.
- **SC-005**: Every live integration test (US1–US7 + hazard arena
  + drop/pickup) reports the same pass result against both
  implementations.
- **SC-006**: Cross-language byte parity holds on every existing
  cross-check fixture: zero discrepancies across Python, the
  standalone Rust crate, and the native package.
- **SC-007**: Substituting `minecraft_bot_accel` for
  `minecraft_bot` in an existing user script requires changing
  exactly the top-level import statements — no other code edits.
- **SC-008**: Median VarInt encode/decode throughput on the
  native side is ≥ 5× faster than the Python reference on a
  representative microbenchmark.
- **SC-009**: Median NBT decode throughput on a 1 KiB payload is
  ≥ 10× faster than the Python reference.
- **SC-010**: Median chunk-decode wall-clock time on a
  representative loaded chunk is ≥ 10× faster than Python.
- **SC-011**: Median A* pathfinder wall-clock time on a 64×64
  navigable test world is ≥ 5× faster than Python.
- **SC-012**: Median physics-tick wall-clock time is ≥ 2× faster
  than Python.
- **SC-013**: Total CPU time for a 60-second normal-play session
  (live-arena hazard course) decreases by ≥ 25% under the native
  package compared to the Python reference.

## Assumptions

- Both `minecraft_bot` and `minecraft_bot_accel` ship as separate
  distributables. They are not co-installed by default; a user
  who wants the native path opts in by installing the accel
  package and changing their imports.
- The native binary uses a stable Python ABI so a single wheel per
  platform covers Python 3.11 and 3.12 (the only supported
  versions).
- Linux wheels target a manylinux baseline broad enough to install
  on stock CI images and modern Linux distros (glibc 2.17+).
- The native `Connection` implementation hosts its own async
  runtime internally; the async bridge translates that into
  Python-visible awaitables that cooperate with the user's
  asyncio loop.
- Native pathfinding and chunk decode operate entirely against
  Rust-owned world state — no per-step Python callbacks needed
  because the World cache lives in Rust on the native side.
- Benchmarks are reproducible across reasonable CI hardware. We
  do not require any specific CPU model.

## Dependencies

- **Milestone 001 (protocol-foundation)** ✓ — provides the codec,
  framer, and all 176 packets for protocol 763 on the Rust side.
- **Milestone 002 (bot-api)** ✓ — defines the public Bot API
  (Bot, World cache, walk_to, observation, drop-item, …) that
  the native implementation must match.
- **External: maturin** — wheel build tooling. Development-time
  only, never a runtime dependency for end users.
- **External: an async-bridging mechanism** — translates between
  the Rust async runtime hosting `Connection` and the Python
  asyncio loop. Required because Bot is async-first.

## Out of Scope

- Online-mode (Mojang authentication). Out of scope through 001
  and remains out of scope here.
- WebAssembly builds. Different target, different toolchain
  configuration.
- Publishing to PyPI. Artefacts are attached to GitHub releases;
  PyPI registration is a separate decision the maintainer makes
  later.
- New protocol versions or new public APIs. This milestone is
  strictly an alternative implementation of the existing surface;
  no feature additions, no protocol-version bumps.
- Removing the Python reference. It stays as the authoritative
  behavioural spec and the development-loop implementation.
