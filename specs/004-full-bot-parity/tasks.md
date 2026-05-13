---
description: "Task list for 004 full bot parity across three backends"
---

# Tasks: Full Bot Parity Across Three Backends

**Input**: Design documents from `/specs/004-full-bot-parity/`
**Prerequisites**: plan.md, spec.md (with `## Clarifications`), research.md, data-model.md, contracts/api-surface.md, quickstart.md
**Tests**: Tests are mandatory for this feature (parity gates are the whole point — see FR-046..FR-048 and US3).

**Organization**: Tasks group by method-area within each user story phase. Because US1/US2/US3 share the same Rust implementation (US3 is the test infrastructure that gates US1 and US2), implementation tasks for method groups are tagged with all three story labels; pure test-infrastructure tasks are US3-only; perf gates are US4-only.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story tag(s). Method groups serve US1+US2+US3 jointly; tagged shorthand `[ALL]` is used to keep lines readable.
- All file paths are repository-relative.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Split the monolithic `rust/src/bot.rs` and `python-ext/src/bot.rs` into per-method-group sub-modules; scaffold new top-level Rust modules (`behaviour/`, `foods.rs`, `recipes.rs`, `inventory/`); accept the one new Cargo dep (`async-trait`); make room for everything else.

- [ ] T001 Split `rust/src/bot.rs` into `rust/src/bot/mod.rs` (re-exports + `Bot` struct) and the empty stubs `rust/src/bot/{state,movement,combat,world_query,inventory,containers,tasks,walk_to,packet_hooks}.rs`. Move existing 003 code (`walk_to`, `packet_hooks`, `connect/disconnect/position/entity_id/health/food/drop_held_item/send_raw`) into the right sub-files. Verify `cargo build -p minecraft_bot` still passes.
- [ ] T002 [P] Split `python-ext/src/bot.rs` mirroring T001: create `python-ext/src/bot/mod.rs` + empty stubs `{state_getters,movement_py,combat_py,world_query_py,inventory_py,containers_py,tasks_py}.rs`. Move existing 003 wrappers. Verify `maturin develop --release` still builds.
- [ ] T003 [P] Add `async-trait = "0.1"` to `rust/Cargo.toml` `[dependencies]`. Add a single-line comment cross-referencing research.md R-5.
- [ ] T004 [P] Create skeleton `rust/src/behaviour/{mod.rs,leaf.rs,leaves/mod.rs}` plus empty `rust/src/behaviour/leaves/{walk_to,eat_when_hungry,follow_entity,attack_target}.rs`. `mod.rs` re-exports `Selector`, `Sequencer`, `Inverter`, `Repeater`, `Leaf`, `NodeStatus`, `BehaviourCtx`, `BehaviourValue`, `BehaviourRunner` (all stubs at this point).
- [ ] T005 [P] Create skeleton `rust/src/foods.rs` with `FoodTable` + `FoodEntry` struct stubs and a `static FOOD_TABLE: OnceLock<FoodTable>` placeholder. Not loaded yet.
- [ ] T006 [P] Create skeleton `rust/src/recipes.rs` with `RecipeIndex` + `RecipeEntry` struct stubs and a `static RECIPE_INDEX: OnceLock<RecipeIndex>` placeholder.
- [ ] T007 [P] Create skeleton `rust/src/inventory/{mod.rs,item.rs,click.rs}`. `item.rs` defines `ItemSlot` (matching data-model.md). `click.rs` is empty.
- [ ] T008 Wire the new modules into `rust/src/lib.rs`: `pub mod behaviour; pub mod foods; pub mod recipes; pub mod inventory;` and `pub use bot::Bot;`. Verify `cargo build -p minecraft_bot` passes.
- [ ] T009 [P] Configure `python-ext/src/lib.rs` to register the new accel sub-modules (`behaviour_py`, `foods_py`). Stub the `behaviour_py.rs` and `foods_py.rs` files as empty `pub fn register(...) -> PyResult<()> { Ok(()) }` placeholders.
- [ ] T010 [P] Add the introspection allow-list scaffold in `python/minecraft_bot/_parity_meta.py`: `PYTHON_ONLY_METHODS = {"_llm_chat_loop", "_llm_observe"}`. (Note: hidden methods already start with `_` so they're filtered; this set is for false-positive carve-outs.)

**Checkpoint**: Workspace compiles, all skeletons exist, no behaviour changed yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the parity-test infrastructure (US3 done criteria) and the data-loading bits other method groups depend on. Nothing in this phase implements a Bot method; everything here is wiring that makes US1/US2 work mechanically and US3 enforceable on day one.

- [ ] T011 [US3] Implement the introspection-based parity collector in `tests/python/parity/_method_collector.py`. Exports `collect_public_methods(cls) -> dict[str, MethodSpec]` where `MethodSpec` has fields `(name, kind, signature, return_type, is_property)`. `kind` is one of `method | property | async_method`. Filter rules: skip names starting with `_`, skip names in `PYTHON_ONLY_METHODS`.
- [ ] T012 [US3] Implement `tests/python/parity/test_bot_full_parity.py`. It calls `collect_public_methods(minecraft_bot.Bot)` and `collect_public_methods(minecraft_bot_accel.Bot)`, asserts the name sets match, then asserts each method's `kind` matches (sync/property/async). Fails verbosely listing all diffs.
- [ ] T013 [US3] Implement `tests/python/parity/test_method_signatures.py`. For each shared method name, compare `inspect.signature` arity (param count) and parameter names; allow type-annotation mismatches if both sides resolve to compatible PyO3 conversions (table in `_parity_meta.py`). Defer return-type comparison to a TODO comment for v0.3.1.
- [ ] T014 [US3] Implement the parity normalizer `tests/python/parity/_parity_normalizer.py`. Exports `normalize_trace(packets, *, backend) -> NormalizedTrace` that strips/zeroes transaction-ids and wall-clock timestamps, plus `compare(trace_py, trace_accel) -> ParityDiff`. The whitelist `TOLERANT_PACKETS = {"finish_break": ["tick"], "entity_status_eat_complete": ["tick"], "cooldown_expiry": ["tick"]}` with `±1 tick` semantics per Q4. Adding a key requires a code-review comment line.
- [ ] T015 [US3] Implement the WireLog capture fixture in `tests/python/parity/_wirelog_fixture.py`. Exports `async def run_method_under_capture(backend, method_call) -> list[Packet]`. Handles both `minecraft_bot` and `minecraft_bot_accel` via duck typing on the `Bot.wire_log` attribute.
- [ ] T016 [US3] Implement the Rust live-smoke harness in `tests/rust/integration_bot_full.rs` (skeleton only, no method tests yet). Module-level `async fn connect_test_bot(username_idx: usize) -> Bot` that picks `TestBot{1..9}` round-robin via `OnceLock<AtomicUsize>`. Server address from `MC_BOT_TEST_SERVER` env var with default `172.26.160.1:25565`.
- [ ] T017 Implement `FoodTable::load()` in `rust/src/foods.rs`: read `protocol-data/v763/items.json`, iterate items whose `foodPoints` field is non-zero, build the `HashMap<u32, FoodEntry>`. Called from `Bot::new` to populate the `OnceLock`. Unit test in `rust/src/foods.rs` `#[cfg(test)]` verifying that bread maps to (5, 6.0) (Minecraft canonical values).
- [ ] T018 [P] Implement `RecipeIndex::load()` in `rust/src/recipes.rs`: read `protocol-data/v763/recipes.json`, for each shaped/shapeless recipe build a row-major 9-cell signature, hash it (FxHash), insert into `by_grid_hash`. Unit test: looking up `[Some("minecraft:oak_planks") × 4, None × 5]` returns `crafting_table` recipe.
- [ ] T019 [P] Implement `ItemSlot::name(&self)` and `ItemSlot::from_slot_data(...)` in `rust/src/inventory/item.rs`. `name` looks up `item_id` in the items table (load via `OnceLock` from `protocol-data/v763/items.json`). Unit tests against three known item ids.
- [ ] T020 [P] Implement `InventoryState::apply_set_slot`, `apply_window_items`, `apply_open_screen`, `apply_close_window` in `rust/src/bot/inventory.rs`. State-machine logic only (no network IO). Unit tests in same file: 8 transitions covering player + container variants.
- [ ] T021 [P] Implement the inventory mutex (`tokio::sync::Mutex`) on the `Bot` struct in `rust/src/bot/mod.rs`. Add helper `Bot::with_inventory_lock<F, R>(&self, f: F) -> R where F: AsyncFnOnce(&mut InventoryState) -> R`.
- [ ] T022 [P] Implement `BehaviourValue`, `BehaviourCtx`, `NodeStatus` enum and the `Leaf` trait in `rust/src/behaviour/leaf.rs`. Pure-Rust unit test: build a small ctx, write/read each variant, verify round-trip.

**Checkpoint**: Parity infrastructure compiles and runs (parity test now reports 60 missing methods on accel, which is expected at this stage). Foods and recipes load on Bot startup. Inventory state machine round-trips. Behaviour-tree value types compile.

---

## Phase 3: User Story Implementation (US1 + US2 + US3, P1+P2)

**Purpose**: Implement each Bot method group. Order matters — later groups depend on earlier ones (containers depend on inventory; tasks depend on movement+combat+world-query+inventory). Each task ports one cohesive group: Rust impl + accel wrap + parity test + live test, in one commit.

### Group A — State accessors (FR-001, 17 accessors)

- [ ] T023 [ALL] Extend `BotState` struct in `rust/src/bot/state.rs` with the 17 fields from data-model.md (yaw, pitch, on_ground, saturation, xp_level, xp_total, game_mode, held_slot, world_name, dimension, is_sneaking, is_sprinting; existing: entity_id, position.x/y/z, health, food). Wire dispatcher updates from `SetHealth`, `SetExperience`, `UpdateGameState`, `Login`, `Respawn`, `PlayerInfoUpdate`.
- [ ] T024 [ALL] Implement Rust accessor methods (`async fn x/y/z/yaw/pitch/on_ground/health/food/saturation/is_dead/xp_level/xp_total/game_mode/held_slot/entity_id/world_name/dimension/position`) in `rust/src/bot/state.rs`. Each reads under `Arc<RwLock<BotState>>`. `is_dead` is derived (`state.health <= 0.0`).
- [ ] T025 [ALL] Implement accel `#[getter]` properties in `python-ext/src/bot/state_getters.rs`. Use `py.allow_threads(|| handle.block_on(rust_async))` per R-1. All 17 + `position` returned as tuple. Verify with `python -c "from minecraft_bot_accel import Bot; print(dir(Bot))"`.
- [ ] T026 [ALL] [P] Parity test `tests/python/parity/test_accessors.py`. Connect Python and accel bot to the live server, read every accessor, compare values (allow ±0.01 on floats since both backends read state-after-arriving-packets which may have nanosecond skew on health regen).
- [ ] T027 [ALL] [P] Live smoke `tests/rust/integration_bot_full.rs::test_state_accessors`. Connect bot, read every accessor, assert sane initial values (health > 0, food > 0, position non-zero).

### Group B — Movement and orientation (FR-002..006, 5 methods)

- [ ] T028 [ALL] Implement `Bot::look_at`, `jump`, `sneak`, `sprint`, `swing_arm` in `rust/src/bot/movement.rs`. Mirror `python/minecraft_bot/bot.py:look_at..swing_arm` line-by-line. `sneak/sprint` track local `is_sneaking`/`is_sprinting` flags and short-circuit on same-value (FR-004 idempotence). `jump` injects 0.42 into `state.velocity.y` and lets the existing physics tick handle the rest.
- [ ] T029 [ALL] Implement accel wrappers in `python-ext/src/bot/movement_py.rs`. All async via `pyo3-async-runtimes::tokio::future_into_py`. Signatures match contracts/api-surface.md row 19..23.
- [ ] T030 [ALL] [P] Parity test `tests/python/parity/test_movement.py`. Per method: connect both backends, run method against the same target, compare packet traces via the normalizer. `look_at` test uses target `(100, 64, 100)` from bot spawn.
- [ ] T031 [ALL] [P] Live smoke for each of the 5 methods in `tests/rust/integration_bot_full.rs::test_movement_*`.

### Group C — Combat and interaction (FR-007..009, 3 methods)

- [ ] T032 [ALL] Implement `Bot::attack`, `interact_entity`, `use_item` in `rust/src/bot/combat.rs`. `attack` reads the current sneak state from `BotState` and includes it in `ServerboundInteract`. `interact_entity` switches between `interact_at` and `interact` based on whether the bot is currently looking at the entity (mirror Python check).
- [ ] T033 [ALL] Implement accel wrappers in `python-ext/src/bot/combat_py.rs`.
- [ ] T034 [ALL] [P] Parity test `tests/python/parity/test_combat.py`. Use the test arena's static dummy mob (op'd `TestBot2` acts as target for `TestBot1`'s attacks; both backends attack the same target eid).
- [ ] T035 [ALL] [P] Live smoke `tests/rust/integration_bot_full.rs::test_combat_*`.

### Group D — World query (FR-010..018, 9 methods)

- [ ] T036 [ALL] Implement `Bot::find_blocks_nearby` in `rust/src/bot/world_query.rs`. Hold a single `WorldQueryGuard` (existing in 003) over the whole search. Iteration order: Chebyshev-nearest-first, then lexicographic `(y, x, z)` (FR-010). Filter accepts `impl Fn(u32) -> bool`.
- [ ] T037 [ALL] Implement `Bot::raycast` in the same file. DDA against block AABBs; tie-breaking matches Python: when ray exactly grazes an edge, prefer the face with the smaller normal in axis order x<y<z.
- [ ] T038 [ALL] Implement `Bot::scan_volume`, `voxel_grid`, `chunks_around`, `world_map_3d` — all read-only iterators over the World cache.
- [ ] T039 [ALL] Implement `Bot::nearby_entities`, `nearby_players`, `distance_to` reading from the entity tracker (already in 003).
- [ ] T040 [ALL] Implement accel wrappers in `python-ext/src/bot/world_query_py.rs`. World-query methods are **sync** on accel (they don't await; they take a read lock and return). `voxel_grid` returns nested `list[list[list[int]]]` per R-1 alt-2 rejection (no NumPy).
- [ ] T041 [ALL] [P] Parity test `tests/python/parity/test_world_query.py`. Pre-load a fixed chunk fixture into both backends' caches via `WireLog.replay`, run each query, compare returned lists element-by-element.
- [ ] T042 [ALL] [P] Live smoke `tests/rust/integration_bot_full.rs::test_world_query_*` — flat arena + a known stone block at `(10005, 200, 10005)`.

### Group E — Observation (FR-019..020, 2 methods)

- [ ] T043 [ALL] Extend `rust/src/observation.rs` with `Bot::snapshot(nearby_radius)` and `Bot::observation()` returning the structs from data-model.md. `snapshot` populates `inventory_summary` by iterating `player_slots` and aggregating by `ItemSlot::name`. `nearby_blocks` is a small voxel sample (radius=4 by default).
- [ ] T044 [ALL] Accel wrappers in `python-ext/src/bot/observation_py.rs` (note: file already exists from 003; extend, don't replace). Both methods are sync.
- [ ] T045 [ALL] [P] Parity test `tests/python/parity/test_observation.py` + live smoke `tests/rust/integration_bot_full.rs::test_observation_*`. Compare returned struct field-by-field.

### Group F — Inventory (FR-021..032, 12 methods + iter_accessible_slots)

- [ ] T046 [ALL] Implement `Bot::held_item`, `find_item`, `count_item` in `rust/src/bot/inventory.rs`. All three read `player_slots` only (Q5 invariant). `find_item` resolves names through `ItemSlot::name`.
- [ ] T047 [ALL] Implement `Bot::iter_accessible_slots` (FR-024a) returning `impl Iterator<Item=(usize, Option<ItemSlot>)>` over `player_slots ++ container_slots`. Verified zero-alloc.
- [ ] T048 [ALL] Implement `Bot::select_slot` in `rust/src/bot/inventory.rs`. Sends `ServerboundHeldItemChange` + updates `BotState.held_slot` locally.
- [ ] T049 [ALL] Implement `Bot::drop_item(drop_stack)` — sends `ServerboundPlayerAction(drop_one|drop_stack)` against currently-held slot. Acquires inventory mutex (R-2).
- [ ] T050 [ALL] Implement `Bot::click_slot(window_id, slot, button, mode, items_changed)` in `rust/src/inventory/click.rs`. Implements the optimistic-update + WindowConfirmation handshake from R-7. 5s timeout; rollback + error on mismatch.
- [ ] T051 [ALL] Implement `Bot::move_item(from, to, count)` in `rust/src/inventory/click.rs`. Sequence: pickup `from`, place `to`, place leftover back (if count != full stack). Matches Python `bot.py:move_item`.
- [ ] T052 [ALL] Implement `Bot::quick_move(slot)` — single click with `button=0, mode=1` (shift-click).
- [ ] T053 [ALL] Implement `Bot::equip_armor(armor_slot, src_slot)` and `unequip_armor(armor_slot, dst_slot)` — both via `quick_move` into the right slot index (5..8).
- [ ] T054 [ALL] Implement `Bot::swap_to_offhand(src_slot)` — `ServerboundPlayerAction(swap_with_offhand)`.
- [ ] T055 [ALL] Accel wrappers for all 12 inventory methods in `python-ext/src/bot/inventory_py.rs`. `held_item` is a `#[getter]` returning `Option<ItemSlot>`; the rest are async methods. Add `ItemSlot` as `#[pyclass(frozen)]` in the same file.
- [ ] T056 [ALL] [P] Parity test `tests/python/parity/test_inventory.py` covering all 12 methods. Read-only methods compared by return value; mutating methods compared via packet trace.
- [ ] T057 [ALL] [P] Live smoke `tests/rust/integration_bot_full.rs::test_inventory_*` — give bot a known kit via `/give @s` issued by the spec server, run move/quick_move/equip/drop sequences.

### Group G — Containers (FR-033..036, 6 methods)

- [ ] T058 [ALL] Implement `Bot::open_block_container(x, y, z, kind, timeout)` in `rust/src/bot/containers.rs`. Subscribes to `OpenScreen` via packet-hook + `tokio::sync::oneshot` per R-8. On success, also subscribes to the first `WindowItems` for the new window_id to populate `container_slots`. Acquires inventory mutex for the duration.
- [ ] T059 [ALL] Implement `Bot::open_chest`, `open_furnace`, `open_crafting_table` as thin wrappers (FR-034) with the correct `ContainerKind` enum value.
- [ ] T060 [ALL] Implement `Bot::close_container` — sends `ServerboundCloseWindow(window_id)`, resets `window_id=0`, clears `container_slots`.
- [ ] T061 [ALL] Implement `Bot::craft(recipe, x, y, z, repeat, timeout)` in `rust/src/bot/containers.rs`. Steps: call `open_crafting_table`, look up recipe via `RecipeIndex` (R-9), for each repeat iteration: pick up ingredients from player_slots, place into crafting grid slots 1..9, take output from slot 0. Sum output counts, return total. Times out per `timeout`.
- [ ] T062 [ALL] Accel wrappers in `python-ext/src/bot/containers_py.rs`. All 6 are async; `open_*` return the `u8` window-id.
- [ ] T063 [ALL] [P] Parity test `tests/python/parity/test_containers.py`. Use the test arena's static chest at a known position (place one for the test in setup). Open, read container_slots, close. Craft test: give bot 4 oak planks, craft a crafting table, verify count.
- [ ] T064 [ALL] [P] Live smoke `tests/rust/integration_bot_full.rs::test_containers_*`.

### Group H — High-level tasks (FR-037..041, 5 methods)

- [ ] T065 [ALL] Implement `Bot::dig(x, y, z, expected_block)` in `rust/src/bot/tasks.rs`. Selects closest face (closest of 6 face-centres to bot eye), sends `ServerboundPlayerAction(start_break, face)`, waits `break_time_ticks` (R-4 formula) via `tokio::time::sleep`, sends `finish_break`. On `expected_block != current_block`, return `Err(BlockChanged)`.
- [ ] T066 [ALL] Implement `Bot::eat(timeout)` in the same file. Find first food slot in hotbar via `FoodTable` lookup, `select_slot` if needed, `swing_arm`, send `ServerboundUseItem`, subscribe to `EntityStatus(eat_complete=24)` via packet hook + oneshot (3s timeout default).
- [ ] T067 [ALL] Implement `Bot::follow(eid, distance, timeout)` — loop: read entity position from tracker, `look_at` it, `walk_to` to `entity_pos - normalize(entity_pos - bot_pos) * distance`. Loop body sleeps 200ms. Exits on distance-reached or timeout.
- [ ] T068 [ALL] Implement `Bot::say(message)` and `Bot::chat(message)` (alias). `say` sends `ServerboundChatMessage` with current Unix ms timestamp and a 64-bit random salt seeded matching Python's RNG init.
- [ ] T069 [ALL] Accel wrappers in `python-ext/src/bot/tasks_py.rs`. All 5 async.
- [ ] T070 [ALL] [P] Parity test `tests/python/parity/test_tasks.py`. `dig` test against a known stone block, allow ±1 tick on `finish_break` tick offset (Q4 whitelist). `eat` test with bread pre-given to bot. `follow` test against `TestBot2` standing still 20 blocks away.
- [ ] T071 [ALL] [P] Live smoke `tests/rust/integration_bot_full.rs::test_tasks_*`.

### Group I — Behaviour trees (FR-042..044, BT-1..BT-10)

- [ ] T072 [ALL] Implement `Selector`, `Sequencer`, `Inverter`, `Repeater` structs in `rust/src/behaviour/mod.rs` — each impls `Leaf`. Children stored as `Vec<Box<dyn Leaf>>` (or single `Box<dyn Leaf>` for Inverter/Repeater).
- [ ] T073 [ALL] Implement `BehaviourRunner` in `rust/src/behaviour/mod.rs` with `tick_dt: Duration`, `cancel: Arc<tokio::sync::Notify>`, and `async fn run(...)` per data-model.md.
- [ ] T074 [ALL] [P] Implement standard leaves in `rust/src/behaviour/leaves/{walk_to,eat_when_hungry,follow_entity,attack_target}.rs`. Each follows the Python equivalent in `python/minecraft_bot/behaviour/leaves.py`.
- [ ] T075 [ALL] Implement `PyLeaf` adapter + `BehaviourCtx <-> PyDict` conversion in `python-ext/src/behaviour_py.rs` per R-6. Exposes `Selector`, `Sequencer`, `Inverter`, `Repeater`, `BehaviourRunner` as `#[pyclass]`. Each `__init__` accepts a list of children that are either `#[pyclass]` Rust leaves OR Python objects with `async def tick(self, bot, ctx)`.
- [ ] T076 [ALL] [P] Parity test `tests/python/parity/test_behaviour.py`. Build the same tree `Selector([EatWhenHungry(15), WalkTo(...)])` on both backends, run for 5 ticks against a controlled scenario, compare packet traces tick-by-tick.
- [ ] T077 [ALL] [P] Live smoke `tests/rust/integration_bot_full.rs::test_behaviour_tree_eat_then_walk`.

---

## Phase 4: Performance gates (US4, P2)

**Purpose**: New world-query perf gates, plus regression check on existing 003 gates.

- [ ] T078 [US4] [P] Add `tests/python/perf/test_speedup_world_query.py` with 3 benches: `find_blocks_nearby` (radius=32, filter stone), `raycast` (32-block ray), `scan_volume` (radius=8). Each asserts accel >= 3x Python. Fixture is a pre-loaded chunk from `tests/python/fixtures/chunk_*.bin`.
- [ ] T079 [US4] [P] Confirm existing 003 gates still pass after the bot.rs split: `pytest tests/python/perf/test_speedup_chunk.py tests/python/perf/test_speedup_varint.py tests/python/perf/test_speedup_physics.py tests/python/perf/test_speedup_pathfinder.py tests/python/perf/test_speedup_nbt.py`. Document any drift in the commit message.

---

## Phase 5: Polish + Release

**Purpose**: Documentation, version bumps, release flow. Runs only after all parity tests are green.

- [ ] T080 Confirm `pytest tests/python/parity -q` is green: 0 failures, 60+ method coverage, introspection test passes. Same for `cargo test --features live-smoke -- --test-threads=1` (~12 method-group live tests).
- [ ] T081 Bump versions in `python/pyproject.toml`, `rust/Cargo.toml`, `python-ext/Cargo.toml`, `python-ext/pyproject.toml`, `python/minecraft_bot/__init__.py`. `python-ext/src/version.rs::PYTHON_COMPAT` -> `"0.3.x"`.
- [ ] T082 Update `CHANGELOG.md` with v0.3.0 entry listing every newly-ported method group (use `contracts/api-surface.md` as source).
- [ ] T083 Update `README.md`: remove "subset" language, restate that all three artefacts share the same Bot API surface. Refresh the artefact table (Surface column for Rust crate + accel now reads "Full Bot surface — see [api-surface.md]"). Add link to `docs/migration_to_accel.md` and update that doc too if it still says subset.
- [ ] T084 Run lint pass: `cargo fmt --all && cargo clippy --all-targets --no-deps -p minecraft_bot -p minecraft_bot_accel || true` (clippy is informational per 003); `ruff check python/ python-ext/ tests/python/ --fix`. Commit any auto-fixes.
- [ ] T085 Merge `004-full-bot-parity` -> `main` (fast-forward). Tag `v0.3.0` on the merge HEAD. `git push origin main && git push origin v0.3.0`. Verify Wheels (003) workflow publishes 6-artefact release (3 accel wheels + 1 py wheel + 1 sdist + 1 .crate).
- [ ] T086 Update `MEMORY.md` (`project_milestone_status.md`): mark 004 done, note v0.3.0 published.

---

## Dependencies

```text
Phase 1 (Setup, T001..T010)
   |
   v
Phase 2 (Foundational, T011..T022)
   |
   v
Phase 3 Group A — accessors (T023..T027)
   |
   v
Phase 3 Group B — movement (T028..T031)
   |
   v
Phase 3 Group C — combat (T032..T035)        [B and C can interleave if separate authors]
   |
   v
Phase 3 Group D — world query (T036..T042)   [D is independent of B/C, can parallelise]
   |
   v
Phase 3 Group E — observation (T043..T045)   [needs D — snapshot reads world]
   |
   v
Phase 3 Group F — inventory (T046..T057)
   |
   v
Phase 3 Group G — containers (T058..T064)    [depends on F — containers use inventory]
   |
   v
Phase 3 Group H — high-level tasks (T065..T071)  [depends on B+C+D+F]
   |
   v
Phase 3 Group I — behaviour trees (T072..T077)   [depends on H — leaves call high-level tasks]
   |
   v
Phase 4 (Performance, T078..T079)
   |
   v
Phase 5 (Release, T080..T086)
```

## Parallel execution opportunities

Within each Phase-3 group, the four sub-tasks (Rust impl, accel wrap, parity test, live test) split as:

- Rust impl is sequential (one author per group).
- Accel wrap can start as soon as Rust impl compiles.
- Parity test `[P]` and live smoke `[P]` can be written in parallel with the accel wrap by a second author.

Across groups: **Movement (B) + World query (D) + Observation (E) can run fully in parallel** — they don't share files or state. Combat (C) shares no state with Movement/Query so it's also fully parallel.

Inventory → Containers → High-level tasks → Behaviour trees is a strict chain.

## Independent test criteria (per spec.md user stories)

- **US1** (import-swap parity, P1): once Phase 3 is complete, take a Python script that calls >=30 distinct Bot methods, run with `import minecraft_bot` vs `import minecraft_bot_accel as minecraft_bot`, confirm identical observable outcomes (SC-003).
- **US2** (Rust-only consumer, P2): `cargo test --features live-smoke -- --test-threads=1` runs to completion with all method-group tests green (SC-005 partial).
- **US3** (enforced parity, P1): `pytest tests/python/parity/test_bot_full_parity.py` reports zero diffs (SC-001 + SC-005).
- **US4** (perf no-regression, P2): `pytest tests/python/perf -q` reports all gates passing including the 3 new ones (SC-004).

## Implementation strategy

**MVP scope**: User Story 3 (enforced parity test) is the most important non-implementation deliverable — it makes the parity claim self-policing. Inside the implementation, the recommended MVP slice is Groups A + B + C + D + E (accessors + movement + combat + world query + observation). This already covers ~35 of the ~60 methods and unblocks anyone writing a "read-only AI agent" that just observes and moves. Inventory/containers/tasks/BT layer on next.

Recommended commit-cadence: one Phase-3 group per commit (9 commits in Phase 3), one commit per Setup task (10 commits in Phase 1), and Phase 2 in 2-3 commits. Total ~25 commits between v0.2.0 and v0.3.0.

## Format validation

All 86 tasks above follow `- [ ] T### [P?] [Story] description with file path`. Setup tasks (T001..T010) and Foundational (T011..T022) carry no story label except where they belong purely to US3 test infrastructure. Method-group tasks (T023..T077) carry `[ALL]` shorthand for US1+US2+US3 since they jointly serve those stories. Perf tasks (T078..T079) carry `[US4]`. Polish (T080..T086) carries no story label.
