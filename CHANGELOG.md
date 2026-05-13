# Changelog

## v0.2.0 (2026-05-12)

First release of the PyO3 native-backed alternative
(`minecraft_bot_accel`). The Python reference (`minecraft_bot`) and
the standalone Rust crate ship in lockstep at the same version.

### Distributables

Three artefacts attach to the GitHub Release:

- **`minecraft_bot`** (pure-Python) — one universal
  `py3-none-any.whl` plus an sdist tarball. Zero runtime deps. This
  is the full reference surface: codec, Connection, dispatcher, world
  cache, A* pathfinder, physics tick, full Bot (`walk_to`, `dig`,
  `attack`, `follow`, `eat`, `say`, behaviour trees, inventory,
  containers, observation snapshot, entity tracker, packet hooks).
- **`minecraft_bot_accel`** (PyO3 facade) — abi3 wheels for Linux
  x86_64, Linux aarch64, macOS arm64, macOS x86_64, Windows x86_64.
  Mirrors the standalone Rust crate's surface: codec, Connection,
  dispatcher, world cache, A* pathfinder, physics tick, and the
  current Bot subset (`connect`, `walk_to`, `drop_held_item`,
  `send_raw`, `on_packet`/`clear_hooks`, `position`,
  `world.is_block_solid`). High-level helpers that are Python-only
  today (dig, attack, follow, eat, behaviour trees, inventory,
  containers, observation snapshot, entity tracker) are not yet on
  the facade; build them as user code on top of the typed Python
  packets plus `send_raw` and `on_packet`, or use the Python
  reference for those flows.
- **`minecraft_bot` (Rust crate)** — `cargo package` tarball
  (`*.crate`). Same surface as the accel facade, callable directly
  from Rust without Python. Install via `cargo install --path` from
  the tarball, or use it as a path/git dependency in another crate.

The three artefacts share the wire protocol byte-for-byte (verified
by `tools/cross_check.py --accel` across 117 fixtures) and share the
same World model, physics model, and pathfinder algorithm. They
differ in **scope**, not behaviour: Python reference is the most
complete; Rust + accel cover the network plus core voxel plus motion
stack.

### Added

- **`minecraft_bot_accel`** PyO3 facade over the standalone Rust
  crate. Drop-in alternative to `minecraft_bot.Bot`: switch one
  import line to run hot paths in Rust.
- **abi3 wheel matrix** in `.github/workflows/wheels.yml`. One wheel
  per (OS, arch) covers Python 3.11 and 3.12. Targets: Linux x86_64,
  Linux aarch64, macOS arm64, macOS x86_64, Windows x86_64.
- **`Bot.send_raw(payload)`** escape-hatch lets callers send any of
  the 176 protocol packets without per-packet PyO3 wrappers. Encode
  through the Python reference's typed dataclasses, forward bytes.
- **Batched codec APIs**: `codec.varint.read_many`,
  `codec.varint.write_many`, `physics.tick_n`. Amortise the FFI
  boundary cost across many ops per call.
- **`codec.nbt`** direct decode/encode of NBT payloads.
- **CPU instrumentation**: `tools/measure_cpu_speedup.py` records
  end-to-end CPU drop for chunk-streaming workloads.
- **Three-way cross-check**: `tools/cross_check.py --accel`
  compares Python, standalone Rust, and accel encoders byte-for-byte
  across 117 fixtures.
- **Docs**: `docs/architecture.md`, `docs/migration_to_accel.md`,
  `docs/examples.md`.

### Performance

Heavy ops and batched primitives consistently beat pure Python.
Per-call codec ops on 1-2 byte values lose to Python because the
PyO3 boundary cost dominates the actual work.

| Operation | Speedup vs Python |
|---|---|
| End-to-end chunk burst (decode + cache + query) | 31.44× |
| Chunk decode alone | 2.84× |
| Batched VarInt read (N=1000) | 26.82× |
| Batched VarInt write (N=1000) | 24.68× |
| NBT decode (real heightmaps payload) | 3.26× |
| Batched physics tick (N=50) | 8.38× |
| A* pathfinder (with snapshot guard) | 6.38× |
| CPU drop during chunk-streaming bursts | 96.8% |

### Tests

- 979 Python unit tests (zero regressions vs 002).
- 88 parity + perf tests covering both backends.
- 76 Rust tests.
- 117 cross-check fixtures with zero discrepancies.
- Live integration against Paper 1.20.1 confirmed for: bot connect,
  position tracking, dispatcher chunk loading, walk_to, drop_held_item.

### Constitutional invariants

- `python/pyproject.toml` still declares `dependencies = []`.
- Nothing in `minecraft_bot` imports from `minecraft_bot_accel`.
- Python remains the spec of record; Rust and accel chase it.

### Motion model and packet hooks

- Accel `walk_to` drives motion through `physics::tick` at 20 Hz
  with the same auto-step, gravity, water drag, and walk-speed cap
  the Python reference uses. Per-tick Player Position packets
  follow the same shape, so anti-cheat and movement-rate behaviour
  matches across backends. Motion-shape parity verified offline by
  `tests/python/parity/test_walk_to_packet_trace.py`; hazard
  traversal verified live by
  `tests/python/integration/test_hazard_arena_parity.py`.
- `Bot.on_packet(packet_id, callback)` lets users subscribe to any
  clientbound packet id. The callback receives `(packet_id, body)`;
  decode the body through the Python reference's typed decoders
  when you need a structured view (see `docs/examples.md`).
  `Bot.clear_hooks()` drops every registration.
- Per-packet typed pyclass wrappers are not shipped. They would
  duplicate the Python reference's 176-packet dataclass surface
  with no new capability. `Bot.send_raw(payload)` covers outbound
  raw sends; `on_packet` covers inbound typed dispatch through the
  Python decoders.

### Codegen fix

- `tools/generate_rust_packets.py` was emitting Rust encoders that
  skipped the trailing `on_ground` byte on the movement packets
  (`flying`, `position`, `look`, `position_look`). The server
  decoded N-1 bytes and disconnected with
  `IndexOutOfBoundsException`. The generator now emits the matching
  encode line for any inline-expr tail field, and the optional-byte
  patcher in turn removes consumed control-flow temps from the
  struct so the dataclass shape stays in sync with the Python
  source. All 176 packets regenerated and pass round-trip tests.

## v0.1.0 (project history snapshot)

Pre-public version. Snapshot of 001-protocol-foundation +
002-bot-api milestones; the Python reference and the standalone Rust
crate were fully usable by then. v0.2.0 is the first release that
includes the PyO3 facade.
