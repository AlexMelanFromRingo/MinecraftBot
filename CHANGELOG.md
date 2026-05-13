# Changelog

## v0.3.0 (2026-05-13)

Full Bot-API parity across all three artefacts (milestone 004).

Every public method on `minecraft_bot.Bot` is now also exposed
by the standalone Rust crate (as `async fn`) and by the
`minecraft_bot_accel` facade (as a sync `#[getter]` property
or an async coroutine, matching the Python ref's shape). The
introspection parity test (`tests/python/parity/test_bot_full_parity.py`)
enforces the contract on every PR — 65 == 65 method names,
zero diff after the `PYTHON_ONLY_METHODS` + `ACCEL_ONLY_METHODS`
allow-lists.

### Added

* **State accessors** (17, FR-001): `x`, `y`, `z`, `yaw`, `pitch`,
  `on_ground`, `health`, `food`, `saturation`, `is_dead`,
  `xp_level`, `xp_total`, `game_mode`, `held_slot`, `entity_id`,
  `world_name`, `dimension`, plus `position` 3-tuple and
  `is_sneaking`/`is_sprinting` toggles. Sync `#[getter]` on accel
  so existing Python scripts read `bot.x` unchanged.
* **Movement** (5, FR-002..006): `look_at`, `jump`, `sneak`,
  `sprint`, `swing_arm`.
* **Combat** (3, FR-007..009): `attack`, `interact_entity`,
  `use_item`.
* **World query** (9, FR-010..018): `find_blocks_nearby`,
  `nearby_entities`, `nearby_players`, `distance_to`, `raycast`
  (DDA voxel walk against World cache), `scan_volume`,
  `voxel_grid`, `chunks_around`, `world_map_3d`.
* **Observation** (2, FR-019..020): `snapshot`, `observation`.
  Accel exposes the structs as Python dicts.
* **Inventory** (12, FR-021..032): dual-list `InventoryState`
  per spec Q5 (`player_slots` persistent, `container_slots`
  transient). `held_item`/`find_item`/`count_item` operate
  only on `player_slots`. New `iter_accessible_slots` helper
  for the explicit merged view. Full click-mode coverage
  (left, right, shift_left, shift_right, swap_offhand, drop).
* **Containers** (6, FR-033..036): `open_block_container`,
  `open_chest`, `open_furnace`, `open_crafting_table`,
  `close_container`, `craft`. Craft takes a 9-cell row-major
  recipe grid per Q2.
* **High-level tasks** (5, FR-037..041): `dig`, `eat`, `follow`,
  `say`, `chat`.
* **Behaviour trees** (FR-042..044): `Selector`, `Sequencer`,
  `Inverter`, `Repeater`, `BehaviourRunner` + standard leaves
  `WalkTo`/`EatWhenHungry`/`FollowEntity`/`AttackTarget`. Closed
  `BehaviourValue` enum keeps the pure-Rust crate free of pyo3
  (R-6). `NodeStatus = Running | Success | Failure`.

### Parity infrastructure

* `tests/python/parity/_method_collector.py` — introspection
  collector with `PYTHON_ONLY_METHODS` and `ACCEL_ONLY_METHODS`
  filtering.
* `tests/python/parity/test_bot_full_parity.py` — symmetric name
  set + property/non-property kind check.
* `tests/python/parity/test_method_signatures.py` — accel
  signature must be subset of Python (Python may expose extra
  optional kwargs).
* `tests/python/parity/_parity_normalizer.py` — packet-trace
  normalizer with the Q4 tolerance whitelist (`finish_break`,
  `entity_status_eat_complete`, `cooldown_expiry` allow ±1 tick
  on a single timing field; everything else is byte-equality).

### Foundational

* `rust/src/foods.rs` — `FoodTable` loaded from
  `protocol-data/v763/food_table.json` via `include_str!`.
* `rust/src/inventory/item.rs` — `ItemSlot` + `ItemTable` loaded
  from `item_table.json`. `name()` resolves item_id → registry
  name with `minecraft:unknown_<id>` fallback.
* `rust/src/bot.rs` dispatcher — new clientbound handlers for
  Login, Respawn, HeldItemSlot, GameStateChange, Experience.
  `walk_to`'s physics tick now writes back x/y/z/on_ground/
  position_known to BotState.
* `python-ext/Cargo.toml` — `multiple-pymethods` pyo3 feature
  enabled so `#[pymethods]` can split across files (one per
  004 method group).
* `rust/Cargo.toml` — `async-trait = "0.1"` added for the
  behaviour-tree `Leaf` trait (R-5).

### Breaking changes vs v0.2.0

* Accel `entity_id`, `health`, `food`, `position` are now sync
  `#[getter]` properties — they were async coroutines in v0.2.0.
  Scripts that did `await bot.health()` need to change to
  `bot.health`. This is the Q1 contract: import-swap parity
  with the Python ref's `@property`.
* `position` returns a 3-tuple `(x, y, z)` instead of v0.2.0's
  5-tuple `(x, y, z, yaw, pitch)`. Use `bot.yaw` / `bot.pitch`
  separately.

### Python-side additions

`python/minecraft_bot/bot.py` grew three new methods for parity:
`iter_accessible_slots`, `eat`, `chat`. `_is_sneaking` /
`_is_sprinting` instance attrs + matching `@property` accessors
mirror the Rust BotState.

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
  x86_64, Linux aarch64, and Windows x86_64. macOS is built locally
  via `maturin develop` (hosted macOS runners are too unreliable to
  ship pre-built Mac wheels in CI).
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
  Linux aarch64, Windows x86_64.
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
