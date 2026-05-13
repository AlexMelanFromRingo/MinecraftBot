# Feature Specification: Full Bot Parity Across Three Backends

**Feature Branch**: `004-full-bot-parity`
**Created**: 2026-05-13
**Status**: Draft
**Input**: User description: "Port the entire Python Bot surface (~60 methods across bot.py, dig.py, behaviour/, observation.py, inventory/, foods.py) to the standalone Rust crate and the PyO3 facade so that `minecraft_bot`, the Rust `minecraft_bot` crate, and `minecraft_bot_accel` expose the identical Bot API. Python remains the spec of record."

## Clarifications

### Session 2026-05-13

- Q: Accessor style on accel — sync property or async method? → A: Accel exposes sync properties (`bot.x`, `bot.health`, …) backed by `Python::with_gil` + blocking poll over the Rust async accessor. Pure Rust crate keeps `async fn` accessors for tokio-embedding consumers. Existing Python user scripts that read `bot.x` continue to work unchanged when they swap the import line.
- Q: Recipe identifier format for `craft` → A: Mirror the Python reference exactly. `craft(recipe: [Option<String>; 9], x: i32, y: i32, z: i32, *, repeat: u32 = 1, timeout: Duration = 8s) -> i32`. The `recipe` parameter is a 9-element row-major grid of Minecraft item-ids (`"minecraft:oak_planks"` or `None` for empty). `(x, y, z)` is the position of the crafting table block. Return value is the count of output items actually produced.
- Q: Inventory state model — single flat list, dual player/container, or full Python mirror? → A: Dual player/container, mirroring the Python `InventoryTracker`. `InventoryState { player_slots: [Option<ItemSlot>; 46], container_slots: Vec<Option<ItemSlot>>, window_id: u8, state_id: i32 }`. `container_slots` is empty when no container window is open. **Invariant**: `held_item()`, `find_item(name)`, `count_item(name)` operate **only** on `player_slots` — opening a chest never silently changes what those return. A separate explicit helper `iter_accessible_slots()` is provided for operations that genuinely need the merged view (e.g., chest-to-inv transfer logic, scripted scanners). The merged view is **derived**, never canonical.
- Q: Packet-trace parity — exact vs tolerant for timing-dependent packets? → A: **Tolerant only for an explicit whitelist** of timing-derived completion packets — currently `finish_break` (dig completion), `EntityStatus(eat_complete)` (eat completion), and cooldown-expiry packets of the same shape. For every other packet (movement, look, attack, swing, click_slot, drop, container open/close, etc.) the comparison is strict byte equality. The whitelist lives in `tests/python/parity/_parity_normalizer.py` and additions require explicit code review. Tolerance is **field-scoped**: only the timing field / send-tick offset may differ, and by at most ±1 tick. Packet kind and payload must match exactly. No "any packet within N ticks" matching — that path degrades quickly into "close enough" and is forbidden.
- Q: Behaviour-tree leaf signature for Rust + accel → A: Mirror the Python `async def tick(self, bot, ctx) -> NodeStatus` shape. Rust trait `Leaf` has `async fn tick(&mut self, bot: &Bot, ctx: &BehaviourCtx) -> NodeStatus`. The context uses a closed value enum (no opaque `PyAny` in the pure-Rust core), so the pure-Rust crate stays free of pyo3:

  ```rust
  pub enum BehaviourValue {
      Int(i64),
      Float(f64),
      Bool(bool),
      String(String),
      Bytes(Vec<u8>),
      Json(serde_json::Value),
  }
  pub type BehaviourCtx =
      Arc<RwLock<HashMap<String, BehaviourValue>>>;
  ```

  `NodeStatus` keeps the canonical BT names `Running | Success | Failure` (not `Continue`) — `Running` carries the specific BT semantics "tick me again next time". The accel facade converts between `BehaviourCtx` and a Python `dict[str, int | float | bool | str | bytes | dict | list]` on each entry/exit so Python users see a regular dict and can mutate it freely. `serde_json::Value` is reserved for future nested/complex use; the initial accel<->Python conversion goes through the primitive variants plus a recursive `serde_json::Value` fallback for nested dicts/lists.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — High-level bot script swaps backends without code changes (Priority: P1)

A developer writes a bot script using the full Bot surface — `walk_to`, `dig`, `attack`, `eat`, `select_slot`, `drop_item`, `say`, `look_at`, `swing_arm`, `find_blocks_nearby`, `snapshot`, `observation`, behaviour trees, etc. They originally imported `minecraft_bot` for development. To ship in production, they change one import line to `minecraft_bot_accel` and the script keeps working with byte-identical packet traces and identical observable outcomes on the live server, but at native speed.

**Why this priority**: This is the single user promise of the project. Without it, the README's claim that three artefacts are interchangeable is misleading. The user has explicitly flagged this as the next thing to fix.

**Independent Test**: Take an existing Python script that exercises the full Bot surface (e.g., `examples/farm_bot.py` if present, otherwise a representative integration test). Run it once against `minecraft_bot` and once against `minecraft_bot_accel` on the live Paper 1.20.1 server. Compare the packet traces captured by `WireLog` — they must match. Compare the final world state (block changes, inventory state, position) — they must match.

**Acceptance Scenarios**:

1. **Given** a bot script that calls `bot.dig(x, y, z)` against a stone block, **When** the same script is run with both backends, **Then** both backends emit the identical `ServerboundPlayerAction(start_break)` → `finish_break` packet sequence with the same timing windows and both observe the block become air in their respective World caches.
2. **Given** a bot script that calls `bot.eat()` while holding bread with food < 20, **When** run on both backends, **Then** both emit `select_slot` (if needed) → `use_item` → wait for `EntityStatus(eat_complete)` and report `bot.food == 20` afterwards.
3. **Given** a bot script that calls `bot.snapshot(nearby_radius=8.0)`, **When** run on both backends in the same world state, **Then** the returned snapshot objects have the same fields with identical values (position, health, food, list of nearby entities, list of nearby block positions).
4. **Given** a behaviour tree `Selector([EatWhenHungry(15), WalkTo(0, 64, 0)])`, **When** run on both backends, **Then** both produce the same sequence of high-level decisions and the same packet trace per tick.

---

### User Story 2 — Rust-only consumer (no Python) can build a full bot directly on the crate (Priority: P2)

A developer building a Rust-only binary (e.g., a desktop bot manager, a benchmark harness, a multi-bot orchestrator) depends on the `minecraft_bot` Rust crate from Cargo. They expect every behaviour the Python reference offers — combat, inventory management, container interaction, behaviour trees, observation snapshots — to be callable from pure Rust with `await`, without any Python runtime in the loop.

**Why this priority**: The standalone Rust crate is a first-class distributable (shipped as a `.crate` tarball in v0.2.0). Today its `Bot` is a 13-method subset; advertising it as a real framework while it's missing dig/attack/inventory/containers is dishonest.

**Independent Test**: Write a Rust integration test (`tests/rust/integration_bot_full.rs`) that connects to Paper 1.20.1, calls each of the 60 methods at least once, and asserts the expected packet trace and post-condition. The test runs under `cargo test --features live-smoke` and passes without linking any Python interpreter.

**Acceptance Scenarios**:

1. **Given** a Rust binary using only `minecraft_bot` as a dependency, **When** it calls `bot.dig(x, y, z, expected_block).await`, **Then** the bot breaks the block and the function resolves successfully (no `pyo3` symbols required).
2. **Given** the same Rust binary, **When** it instantiates `Selector::new(vec![Box::new(EatWhenHungry::new(15)), Box::new(WalkTo::new(0.0, 64.0, 0.0))])` and runs it through `BehaviourRunner`, **Then** the runner ticks the tree and produces the same outcomes as the Python `behaviour.BehaviourRunner`.

---

### User Story 3 — Three-way parity is enforced by automated tests on every PR (Priority: P1)

A maintainer adds a new method to the Python Bot. The repository's CI surfaces the divergence immediately — a parity test fails because the Rust and accel backends don't ship the same method — so the maintainer is forced to port the method (or explicitly mark it as Python-only) before the PR can land.

**Why this priority**: Without automated enforcement, the three implementations will drift again the moment 004 ships. The user said the README claim must become true and stay true.

**Independent Test**: Run `pytest tests/python/parity/test_bot_full_parity.py` — it discovers all public methods on `minecraft_bot.Bot` via introspection and asserts the same method exists on `minecraft_bot_accel.Bot` (with the same signature, modulo Rust→Python type mapping). Optional explicit allow-list (`PYTHON_ONLY_METHODS = {"_llm_chat_loop", ...}`) for methods that should NOT be ported.

**Acceptance Scenarios**:

1. **Given** the introspection test scans `Bot` on both backends, **When** the lists are compared, **Then** the symmetric difference (excluding the explicit allow-list) is empty.
2. **Given** the per-method packet-trace test runs each method on both backends with WireLog capture, **When** the captured traces are diffed, **Then** they are byte-identical except for fields the spec marks as non-deterministic (e.g., timing-derived `transaction_id` values, which are normalised before comparison).

---

### User Story 4 — Performance does not regress (Priority: P2)

The user's existing performance gates (chunk decode 31×, batched VarInt 25×, A* pathfinder 6×) continue to pass after 004 lands. Newly ported methods that have a clear native-speed advantage (`find_blocks_nearby`, `raycast`, `scan_volume`, `voxel_grid`, behaviour-tree tick) show measurable speedup on the accel backend.

**Why this priority**: The promise of the accel backend is speed. If 004 ports every method but does so via slow Python-callback chains, the project loses its reason to exist.

**Independent Test**: `pytest tests/python/perf/test_speedup_*.py` — existing gates pass unchanged. Add `test_speedup_world_query.py` covering `find_blocks_nearby`, `raycast`, `scan_volume` and require >=3x speedup on the accel backend vs. Python.

**Acceptance Scenarios**:

1. **Given** the existing perf suite, **When** run after 004 lands, **Then** every existing gate passes with the same margin or better.
2. **Given** the new world-query perf tests, **When** run on the accel backend, **Then** each method beats Python by at least 3x.

---

### Edge Cases

- **Method that needs a Python-side type with no clean Rust equivalent** (e.g., a `numpy.ndarray` returned by `voxel_grid` in some Python codepaths). Decision: the Rust crate returns a flat `Vec<u16>` plus shape `(usize, usize, usize)`; the accel `#[pymethods]` wrapper converts to a Python `list[list[list[int]]]` (no NumPy dep, per Constitution VI). If the Python reference returns NumPy when NumPy is installed, that is a Python-only opt-in path documented in migration notes — the parity test asserts equality on the list form.
- **Method that depends on a Python-only library** (LLM agent in `python/minecraft_bot/llm_agent/`). Explicitly out of scope; goes on the `PYTHON_ONLY_METHODS` allow-list with a comment pointing to this spec.
- **Concurrent mutation of inventory while a `craft` call is in flight**. The Rust implementation, like Python, MUST serialise inventory-modifying calls per-Bot via a `tokio::sync::Mutex` to match Python's `asyncio.Lock`.
- **Behaviour tree with a leaf that calls back into Python** (user-supplied custom leaf in a Python script using `minecraft_bot_accel`). The accel facade MUST support passing Python callables as leaves and call them with `Python::with_gil` from the runner.
- **`look_at` against a target on the same Y as the bot's eyes**. Both backends MUST produce the same pitch (0.0) and same yaw, including the same handling of the `atan2` edge case at exactly `(0, 0)`.
- **`dig` on a block that breaks instantly** (flower, tall grass). Both backends MUST send the abort-break-time path: `start_break` immediately followed by `finish_break` with no wait.
- **`eat` when there is no food in the hotbar**. Both backends MUST raise the same exception type (Python `NoFoodError`; Rust `Err(ProtocolError::NoFood)`; accel converts Rust error into Python `NoFoodError`).
- **`open_chest` against a block that is not a chest**. Both backends MUST time out waiting for `OpenScreen` and raise the same error (Python `ContainerOpenError`; same conversion path).

## Requirements *(mandatory)*

### Functional Requirements

**State accessors (read-only):**

- **FR-001**: The accel `Bot` MUST expose accessors as **sync Python properties** (`bot.x`, `bot.health`, …) so existing Python user scripts that read these attributes work unchanged when the import is swapped from `minecraft_bot` to `minecraft_bot_accel`. The pure-Rust `Bot` keeps `async fn` accessors for tokio-embedding consumers. The accel `#[pymethods]` `#[getter]` wrappers acquire `Python::with_gil`, drive the Rust async accessor to completion via the existing tokio runtime, and return the resolved value. Accessors covered: `x`, `y`, `z`, `yaw`, `pitch`, `on_ground`, `health`, `food`, `saturation`, `is_dead`, `xp_level`, `xp_total`, `game_mode`, `held_slot`, `entity_id`, `world_name`, `dimension`.

**Movement & orientation:**

- **FR-002**: `Bot::look_at(x, y, z)` MUST compute yaw and pitch from the bot's current position to the target and send a single `ServerboundLook` packet identical to the Python reference's output (yaw/pitch within +/-0.01 degrees to account for f32/f64 differences).
- **FR-003**: `Bot::jump()` MUST inject an upward impulse into the physics state (initial Y velocity matching the Python reference's `JUMP_IMPULSE = 0.42`) and the next physics-tick Player Position packet MUST reflect the new altitude.
- **FR-004**: `Bot::sneak(enabled)` MUST send `ServerboundEntityAction(start_sneaking)` when transitioning false->true and `stop_sneaking` when transitioning true->false. Calling with the same value twice MUST be a no-op (no packet).
- **FR-005**: `Bot::sprint(enabled)` MUST behave identically using `start_sprinting`/`stop_sprinting`.
- **FR-006**: `Bot::swing_arm(hand)` MUST send `ServerboundSwingArm` with the given hand (0=main, 1=off).

**Combat & interaction:**

- **FR-007**: `Bot::attack(eid)` MUST send `ServerboundInteract` with `action=attack`, `target_eid=eid`, `sneaking=current_sneak_state`.
- **FR-008**: `Bot::interact_entity(eid, hand)` MUST send `ServerboundInteract` with `action=interact_at` (or `action=interact` if the bot is not looking at a specific spot on the entity, matching Python).
- **FR-009**: `Bot::use_item(hand)` MUST send `ServerboundUseItem` with the given hand.

**World query (read-only, against World cache):**

- **FR-010**: `Bot::find_blocks_nearby(filter, radius, limit)` MUST return up to `limit` block positions within `radius` of the bot whose state-id matches `filter`. Iteration order MUST match the Python reference (nearest-first by Chebyshev distance, then lexicographic by `(y, x, z)`).
- **FR-011**: `Bot::distance_to(eid)` MUST return `Option<f64>` (Euclidean distance, or `None` if entity not tracked).
- **FR-012**: `Bot::nearby_entities(radius)` MUST return a list of `EntityRef { eid, type, position, distance_from_bot }` sorted by distance ascending.
- **FR-013**: `Bot::nearby_players(radius)` MUST behave like FR-012 filtered to player entities.
- **FR-014**: `Bot::raycast(max_distance)` MUST DDA-trace a ray from the bot's eye position along its look vector and return the first hit `(block_pos, face)` or `None`. Tie-breaking rules MUST match the Python reference.
- **FR-015**: `Bot::scan_volume(radius, include_air)` MUST return a list of `(BlockPos, state_id)` for every block in a `(2*radius+1)^3` cube around the bot, filtered by `!include_air` if requested.
- **FR-016**: `Bot::voxel_grid(radius)` MUST return a 3D array (flat `Vec<u16>` of length `(2*radius+1)^3` in Rust; nested Python list in accel) of state-ids.
- **FR-017**: `Bot::chunks_around(radius_chunks)` MUST return a list of `(cx, cz)` for every chunk currently loaded in the cache within `radius_chunks` of the bot's chunk.
- **FR-018**: `Bot::world_map_3d(radius_xz, radius_y)` MUST return the same shape as `voxel_grid` but with independent radii on the XZ plane vs the Y axis.

**Observation:**

- **FR-019**: `Bot::snapshot(nearby_radius)` MUST return a frozen snapshot struct containing bot state (position, look, health, food, inventory summary), nearby entities filtered to `nearby_radius`, and nearby blocks (small voxel sample at `nearby_radius`). Field names and types in the accel snapshot MUST match the Python `BotSnapshot` dataclass.
- **FR-020**: `Bot::observation()` MUST return a lighter-weight observation suitable for high-frequency AI loops (no nearby blocks, no full inventory). Format identical across backends.

**Inventory:**

- **FR-021**: Each backend MUST maintain `InventoryState { player_slots: [Option<ItemSlot>; 46], container_slots: Vec<Option<ItemSlot>>, window_id: u8, state_id: i32 }`. Player slot layout: slot 0 = crafting result, 1..4 = crafting grid, 5..8 = armor (helmet/chest/legs/boots), 9..35 = main inventory, 36..44 = hotbar, 45 = offhand. `container_slots` is empty when no container window is open; populated from `WindowItems` on `open_*`, cleared on `close_container`. Both slot vectors are updated from clientbound `SetSlot` and `WindowItems` packets according to which window-id and slot index the packet carries.
- **FR-022**: `Bot::held_item()` MUST return `player_slots[36 + held_slot]` (or `None` if empty). It MUST NOT consult `container_slots`.
- **FR-023**: `Bot::find_item(name)` MUST return the first index into `player_slots` matching `name` (by Minecraft item-id from `protocol-data/v763/items.json`) or `None`. It MUST NOT consult `container_slots`.
- **FR-024**: `Bot::count_item(name)` MUST sum item counts across `player_slots` only.
- **FR-024a**: `Bot::iter_accessible_slots()` MUST return an iterator that yields `(slot_index, Option<ItemSlot>)` over both `player_slots` and the currently-open `container_slots`. This is the **only** API path that exposes the merged view; it MUST be derived on each call and MUST NOT be cached as canonical state.
- **FR-025**: `Bot::select_slot(hotbar_index)` MUST send `ServerboundHeldItemChange` and update `held_slot` locally.
- **FR-026**: `Bot::drop_item(drop_stack)` MUST send `ServerboundPlayerAction(drop_one)` or `drop_stack` against the currently-held slot.
- **FR-027**: `Bot::click_slot(window_id, slot, button, mode, items_changed)` MUST send `ServerboundClickWindow`. State-id and transaction-id are managed by the implementation.
- **FR-028**: `Bot::move_item(from, to, count)` MUST perform the click sequence (pickup -> place) equivalent to the Python reference. The exact click order is asserted by parity tests.
- **FR-029**: `Bot::quick_move(slot)` MUST send a shift-click (`button=0, mode=1`).
- **FR-030**: `Bot::equip_armor(armor_slot, src_slot)` MUST quick-move the source slot into the correct armor slot (5=helmet, 6=chestplate, 7=leggings, 8=boots).
- **FR-031**: `Bot::unequip_armor(armor_slot, dst_slot)` MUST quick-move the armor slot to `dst_slot`.
- **FR-032**: `Bot::swap_to_offhand(src_slot)` MUST send `ServerboundPlayerAction(swap_with_offhand)`.

**Containers:**

- **FR-033**: `Bot::open_block_container(x, y, z, kind)` MUST send `ServerboundUseItemOn` at the block face pointing toward the bot and await a clientbound `OpenScreen` matching `kind`. Returns the new window-id. Times out after 5 seconds.
- **FR-034**: `Bot::open_chest`, `open_furnace`, `open_crafting_table` MUST be thin aliases over FR-033 with the appropriate `kind`.
- **FR-035**: `Bot::close_container()` MUST send `ServerboundCloseWindow` for the current open window and reset internal state.
- **FR-036**: `Bot::craft(recipe, x, y, z, *, repeat=1, timeout=8s)` MUST mirror the Python reference's signature exactly: `recipe` is a 9-element row-major grid of `Option<String>` Minecraft item-ids (`"minecraft:oak_planks"` or `None` for empty), `(x, y, z)` is the crafting-table block position, `repeat` is how many times to craft the recipe, `timeout` is the upper bound on completion. The method opens the crafting table (via `open_crafting_table`), performs the click sequence to place ingredients into the 3x3 grid for each repeat, takes the result, and returns the count of output items actually received. Recipe resolution uses the same `protocol-data/v763/recipes.json` table both backends already ship.

**High-level tasks:**

- **FR-037**: `Bot::dig(x, y, z, expected_block)` MUST select the closest face of the block, send `ServerboundPlayerAction(start_break)`, wait the break-time computed from the block's hardness and the held tool, then send `finish_break`. If `expected_block` is supplied, the call MUST short-circuit when the block is no longer the expected block (returns `Err(BlockChanged)`).
- **FR-038**: `Bot::eat()` MUST find the first food item in the hotbar, `select_slot` to it, send `use_item`, await `EntityStatus(eat_complete)`. Times out after 3 seconds. If no food, returns `Err(NoFood)`.
- **FR-039**: `Bot::follow(eid, distance, timeout)` MUST repeatedly `look_at` and `walk_to` toward the entity until within `distance` or `timeout` expires.
- **FR-040**: `Bot::say(message)` MUST send `ServerboundChatMessage` with the current timestamp and a random salt matching the Python reference's RNG seeding rules.
- **FR-041**: `Bot::chat(message)` MUST be an alias for `say`.

**Behaviour trees:**

- **FR-042**: Rust `behaviour` module MUST expose `Selector`, `Sequencer`, `Inverter`, `Repeater`, `Leaf` traits/structs and a `BehaviourRunner` with a `tick_dt` duration matching the Python `behaviour.nodes` module. Leaf signature:
  ```rust
  #[async_trait]
  pub trait Leaf: Send + Sync {
      async fn tick(&mut self, bot: &Bot, ctx: &BehaviourCtx) -> NodeStatus;
      fn reset(&mut self) {}
  }
  pub enum NodeStatus { Running, Success, Failure }
  pub enum BehaviourValue { Int(i64), Float(f64), Bool(bool), String(String), Bytes(Vec<u8>), Json(serde_json::Value) }
  pub type BehaviourCtx = std::sync::Arc<parking_lot::RwLock<std::collections::HashMap<String, BehaviourValue>>>;
  ```
  The pure-Rust core does not import `pyo3`.
- **FR-043**: Standard leaves: `WalkTo`, `EatWhenHungry(threshold)`, `FollowEntity(eid, distance)`, `AttackTarget(eid)`. Behaviour identical to Python `behaviour.WalkTo`, `EatWhenHungry`, etc.
- **FR-044**: Accel facade MUST allow Python objects with an `async def tick(self, bot, ctx)` method to be used as leaves. The runner calls them via `Python::with_gil` and awaits the returned coroutine through `pyo3-async-runtimes::tokio`. The accel layer converts `BehaviourCtx` to/from a Python `dict[str, int | float | bool | str | bytes | dict | list]` on each entry and exit so Python users see and mutate a normal dict. Nested dicts/lists round-trip through the `BehaviourValue::Json(serde_json::Value)` variant.

**Food table:**

- **FR-045**: `rust/src/foods.rs` MUST contain the same food-id -> (hunger_restore, saturation_restore) table the Python `foods.py` ships, sourced from `protocol-data/v763/items.json` foods section.

**Parity test infrastructure:**

- **FR-046**: A pytest collector MUST introspect both `minecraft_bot.Bot` and `minecraft_bot_accel.Bot` and assert symmetric method coverage modulo `PYTHON_ONLY_METHODS`.
- **FR-047**: For each method (excluding accessors and Python-only methods), a parity test MUST capture the packet trace under both backends and assert byte-equality, with the narrow whitelist defined in SC-002 (timing-derived completion packets: `finish_break`, `EntityStatus(eat_complete)`, cooldown-expiry). Transaction ids and wall-clock timestamps are normalised before comparison. Tolerance applies field-scoped (timing field, +/-1 tick); packet kind and payload must match exactly.
- **FR-048**: A `cargo test --features live-smoke` integration suite MUST exercise every Rust `Bot` method against the live Paper 1.20.1 server.

**Version & docs:**

- **FR-049**: Version MUST be bumped to `0.3.0` in `python/pyproject.toml`, `rust/Cargo.toml`, `python-ext/Cargo.toml`, `python-ext/pyproject.toml`, `python/minecraft_bot/__init__.py`, and `python-ext/src/version.rs` (PYTHON_COMPAT = "0.3.x").
- **FR-050**: README MUST state that all three artefacts share the same Bot API surface. CHANGELOG MUST add a v0.3.0 entry listing every newly-ported method.

### Key Entities

- **BotState (Rust + accel)**: Internal mutable state of a connected Bot. Fields: `entity_id`, `position`, `yaw`, `pitch`, `on_ground`, `health`, `food`, `saturation`, `xp_level`, `xp_total`, `game_mode`, `held_slot`, `world_name`, `dimension`, `is_sneaking`, `is_sprinting`. Mirrors the Python Bot's instance attributes 1:1.
- **InventoryState (Rust + accel)**: Dual-list model mirroring the Python `InventoryTracker`. Fields: `player_slots: [Option<ItemSlot>; 46]` (persistent), `container_slots: Vec<Option<ItemSlot>>` (transient, populated only while a container window is open), `window_id: u8`, `state_id: i32`, `last_click_transaction_id: u32`. Updated from `SetSlot`, `WindowItems`, `SetCarriedItem`. The merged "all visible slots" view is derived via `iter_accessible_slots()` and is never cached.
- **BotSnapshot (all three)**: Frozen observation struct returned by `snapshot()`. Same field set on all three backends.
- **Observation (all three)**: Lightweight observation struct returned by `observation()`. Subset of `BotSnapshot`.
- **EntityRef (Rust + accel)**: Read-only view over a tracked entity: `eid`, `type`, `position`, `distance_from_bot`.
- **TickResult enum (Rust + accel)**: `Continue | Success | Failure`. Same name and semantics as Python.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All Python `Bot` public methods (~60) are callable on `minecraft_bot.Bot`, `minecraft_bot` (Rust crate), and `minecraft_bot_accel.Bot` with the same name and the same signature (modulo Rust-Python type mapping rules documented in `contracts/api-surface.md`).
- **SC-002**: For each non-accessor method, packet-trace parity tests show byte-identical clientbound/serverbound exchanges across all three backends on the same scripted scenario, **with one narrow exception**: a small explicit whitelist of timing-derived completion packets (`finish_break`, `EntityStatus(eat_complete)`, cooldown-expiry packets) may differ on the timing field / send-tick offset by at most +/-1 tick. Packet kind and payload must still match exactly. The whitelist is enforced by `tests/python/parity/_parity_normalizer.py`; additions require code review.
- **SC-003**: A user script that imports `minecraft_bot` and exercises >=30 distinct Bot methods runs to completion against the live Paper 1.20.1 server. The same script with the single import line swapped to `minecraft_bot_accel` runs to completion with the identical observable outcomes (final position within 0.1 block, identical inventory state, identical world deltas).
- **SC-004**: All existing performance gates pass unchanged after 004 lands. New `find_blocks_nearby`/`raycast`/`scan_volume` perf tests show >=3x speedup on accel vs Python.
- **SC-005**: CI runs the parity suite, the existing 979 unit tests, and 88+ parity/perf tests; all pass on every commit to `main`.
- **SC-006**: README and CHANGELOG describe the three artefacts as having the **same** Bot surface (no more "subset" language).
- **SC-007**: A new GitHub release `v0.3.0` ships with the same three artefact types as v0.2.0 (3 accel wheels + 1 pure-Python wheel + 1 sdist + 1 Rust crate tarball).

## Assumptions

- Python remains the spec of record. Any behaviour discrepancy discovered during parity testing is resolved by changing Rust/accel to match Python, never the reverse.
- The 60-method estimate covers the Python Bot's current public surface as of commit 41492c2. New methods added to Python during 004 implementation will be ported in the same PR (parity is a hard gate).
- `pyo3-async-runtimes::tokio` (already in `python-ext/`) is sufficient to bridge async methods that need to await server responses (`open_chest`, `dig`, `eat`).
- The block-hardness table needed for `dig` break-time calculation already exists in `protocol-data/v763/block_states.json`.
- The recipe table for `craft` already exists in `protocol-data/v763/recipes.json`.
- macOS continues to be supported via the pure-Python wheel and local `maturin develop`; no macOS wheels are added in this milestone (carry-over from 003).
- The user's existing test arena at `(10000, 200, 10000)` with op'd `TestBot1..9` and `WalkBot1..3` remains available for live tests throughout 004 implementation.
- LLM agent module (`python/minecraft_bot/llm_agent/`) is intentionally Python-only and is excluded from parity by explicit allow-list.
