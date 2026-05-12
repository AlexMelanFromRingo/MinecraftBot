---
description: "Task list for Bot API (002-bot-api)"
---

# Tasks: Bot API

**Input**: Design documents from `/specs/002-bot-api/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present); milestone 001 must be merged or available on the branch (it is, as 002 branches from 001-protocol-foundation HEAD).
**Tests**: Included — spec FR-140 (each public Bot method tested) and FR-141 (live-server smoke for P1) explicitly require them.
**Branch**: `002-bot-api`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Different files, no incomplete dependencies
- **[Story]**: US1..US7 for user-story tasks; Setup/Foundational/Polish phases carry no label
- All paths repo-relative; absolute root is `/home/young-developer/my_todo/MinecraftBot`

## Path Conventions

Per `plan.md` Project Structure (additive on top of 001):

- Python core: `python/minecraft_bot/` (existing 001 untouched; new submodules: `bot.py`, `world/`, `entities/`, `inventory/`, `physics.py`, `pathfinding.py`, `behaviour/`, `events.py`, `slots.py`)
- Shared data: `protocol-data/v763/` (new: `block_states.json`, `entity_metadata.json`, `foods.json`, `entity_hitboxes.json`)
- Tests: `tests/python/` (new test files alongside the 001 ones)
- Tools: `tools/` (new: `generate_entity_subclasses.py`, `fetch_block_states.py`, `fetch_foods.py`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Land the new module directories, fetch the per-version data tables (block states, entity metadata, foods, hitboxes), wire the codegen tool for entity subclasses.

- [X] T001 Create new module dirs: `python/minecraft_bot/world/`, `python/minecraft_bot/entities/`, `python/minecraft_bot/entities/types/`, `python/minecraft_bot/inventory/`, `python/minecraft_bot/behaviour/`. Add empty `__init__.py` to each.
- [X] T002 Create `tools/fetch_block_states.py` — one-shot fetcher that pulls `data/pc/1.20/blocks.json` from PrismarineJS minecraft-data and converts it to `protocol-data/v763/block_states.json` with `{state_id: {name, properties}}`.
- [X] T003 Run T002 to populate `protocol-data/v763/block_states.json` (~21000 entries).
- [X] T004 Create `tools/fetch_foods.py` — pulls `data/pc/1.20/foods.json` from minecraft-data and writes `protocol-data/v763/foods.json` with `{item_id: {food_points, saturation_modifier, can_always_eat}}`.
- [X] T005 Run T004 to populate `protocol-data/v763/foods.json`.
- [X] T006 Create `protocol-data/v763/entity_metadata.json` derived from minecraft-data's `entities.json` + `protocol.json` entityMetadata switch table. One entry per entity-type-id with `{name, parent, metadata_indices: [{index, type, name}]}`. Hand-edit if upstream is incomplete; document in `protocol-data/v763/README.md`.
- [X] T007 Create `protocol-data/v763/entity_hitboxes.json` from minecraft.wiki "Entity" tables — `{entity_type_name: {width, height}}` AABB for collision.
- [X] T008 [P] Create `tools/generate_entity_subclasses.py` scaffold — reads `entity_metadata.json`, emits one file per entity type at `entities/types/{snake_name}.py` with typed accessors. Idempotent (`--force` reruns; preserves hand-edits outside auto-generated blocks).
- [X] T009 [P] Update `tests/python/conftest.py` if new fixtures needed (probably no change; the existing `live_server` + throttle fixture covers 002).

**Checkpoint**: Skeleton dirs ready, all data tables on disk, codegen tool present.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement the cross-cutting substrate every user story depends on. ⚠ CRITICAL — no US-tagged work can begin before this phase is complete.

### Slot model + events + errors

- [X] T010 Implement `python/minecraft_bot/slots.py` — `BotBusy` exception, slot-lock helpers (`MovementSlot`, `ActionSlot`, `ContainerSlot`), each wrapping `asyncio.Lock` with `__aenter__` / `__aexit__` and a `wait_for_slot` flag (raises `BotBusy` if already held and `wait_for_slot=False`).
- [X] T011 [P] Unit test slot model at `tests/python/unit/test_slot_model.py` — verify concurrent acquire raises `BotBusy` when `wait_for_slot=False`, queues when `True`, releases on exception.
- [X] T012 Implement `python/minecraft_bot/events.py` — base `Event` + 13 concrete dataclasses per FR-101 (ChatMessageEvent, EntityDamageEvent, EntityDeathEvent, ItemPickupEvent, InventoryChangeEvent, BlockBreakEvent, ContainerOpenEvent, ContainerCloseEvent, TeleportedEvent, InLavaEvent, DimensionChangedEvent, RespawnEvent; re-export `Reconnected` from 001).
- [X] T013 Extend 001's `python/minecraft_bot/errors.py` with new exceptions (in-place edit): `NoPathFound`, `WalkTimeout`, `DigFailed`, `TargetLost`, `ContainerClosed`, `InventoryStateMismatch`, `InVehicle`. All extend `ProtocolError`.

### Block-state table

- [X] T014 Implement `python/minecraft_bot/world/block_table.py` — loads `protocol-data/v763/block_states.json` at import time, exposes `get_name(state_id) -> str | None`, `get_properties(state_id) -> dict`, plus classification predicates `is_solid(state_id)`, `is_water(state_id)`, `is_navigable_obstacle(state_id)`, `step_height(state_id) -> float` (for slabs/stairs). Rules built from name + properties (e.g., `is_solid = state.name not in PASSTHROUGH_NAMES`).
- [X] T015 [P] Unit test block table at `tests/python/unit/test_block_table.py` — every state_id resolves to a name; spot-check classifications for stone (solid), air (not solid), water (water), oak_door[open=true] (navigable obstacle), oak_slab[type=top] (step height 0.5).

### Chunk decoder + paletted containers

- [X] T016 Implement `python/minecraft_bot/world/chunk.py` — `PalettedContainer` (with bits_per_entry, palette, long-packed data, single_value mode), `ChunkSection` (block_count + block_states PalettedContainer + biomes PalettedContainer), `Chunk` (cx, cz, sections, biomes, block_entities, heightmaps), `Chunk.get_block(local_x, y, local_z) -> int`.
- [X] T017 Implement `python/minecraft_bot/world/decode_chunk.py` — structured decoder for the `map_chunk` packet's `payload` bytes (currently opaque in 001). Parses heightmaps NBT, then per section: short block_count + paletted block-state container + paletted biomes container. Returns a `Chunk`.
- [X] T018 [P] Unit test chunk decode at `tests/python/unit/test_chunk_decode.py` — paletted container in all three modes (single_value, indexed, direct); chunk with mixed empty + populated sections; block_entities NBT round-trip. Use synthetic byte payloads + a real captured chunk from `protocol-data/v763/live_captures/`.

### A* pathfinder (pure function)

- [X] T019 Implement `python/minecraft_bot/pathfinding.py` — 8-dir A* with octile heuristic, `heapq` open-set, configurable `max_fall`, `max_nodes` budget; consumes a World-like interface (only needs `is_solid` / `is_navigable` / `is_water` queries) so it's testable offline. Raises `NoPathFound` if A* exhausts open set or budget.
- [X] T020 [P] Unit test pathfinder at `tests/python/unit/test_pathfinding.py` — ASCII-art synthetic worlds: flat path, step-up, gap-jump, water swim, doored path, walled-off (raise NoPathFound), narrow corridor with diagonals.

### Physics tick (pure function)

- [X] T021 Implement `python/minecraft_bot/physics.py` — `PhysicsState` dataclass, `tick(state, world, inputs) -> new_state` pure function. Constants for gravity (0.08), friction (0.91 ground, 0.546 air, 0.8 water), step-up (0.6), water buoyancy. AABB sweep collision against world voxels.
- [X] T022 [P] Unit test physics at `tests/python/unit/test_physics.py` — synthetic worlds: free-fall trajectory, step-up over 1-block ledge, water entry decelerates, friction stops motion when no input, collision with wall.

### Entity metadata stream codec + base classes

- [X] T023 Implement `python/minecraft_bot/entities/metadata.py` — full stream codec for the `entity_metadata` packet's payload (replaces 001's opaque bytes). Type table covers all 28 metadata-value types from 1.20.1 (Byte, VarInt, VarLong, Float, String, Chat, OptChat, Slot, Bool, Rotations, Position, OptPosition, Direction, OptUUID, BlockState, OptBlockState, NBT, Particle, VillagerData, OptVarInt, Pose, CatVariant, FrogVariant, OptGlobalPos, PaintingVariant, SnifferState, Vec3f, Quaternion). Stream terminates on `index == 0xFF`.
- [X] T024 [P] Unit test entity metadata codec at `tests/python/unit/test_entity_metadata.py` — round-trip every type; mixed-type compound stream; truncation/0xFF terminator behaviour.
- [X] T025 Implement `python/minecraft_bot/entities/base.py` — `Entity` (id, uuid, type, position, yaw, pitch, head_yaw, velocity, metadata, on_ground), `Living(Entity)` (health, is_baby, pose, custom_name, custom_name_visible), `Mob(Living)`, `Player(Living)`, `ItemEntity(Entity)`, `Projectile(Entity)`, `Vehicle(Entity)`. Frozen-but-mutable-state design (use `__slots__` + replace via `dataclasses.replace`).

### Window-click protocol helper

- [X] T026 Implement `python/minecraft_bot/inventory/window.py` — high-level operations `pickup`, `pickup_half`, `quick_move`, `swap_with_hotbar`, `drop_one`, `drop_stack`, `clone`. Each produces the appropriate `WindowClick` packet (mode/button/changed_slots/carried_item) using server's last-known `state_id`. Optimistic state delta included.
- [X] T027 [P] Unit test window-click at `tests/python/unit/test_inventory_click.py` — for each operation, assert the resulting `WindowClick` packet has expected mode/button. State_id increments correctly. State mismatch raises `InventoryStateMismatch`.

### Food table + pickers

- [X] T028 Implement `python/minecraft_bot/inventory/food.py` — load `foods.json` at import; export `is_food(item_id) -> bool`, `food_value(item_id) -> tuple[int, float, bool]`. Implement pickers `BEST_SATURATION`, `WORST_FIRST`, `OLDEST_FIRST` per FR-090.
- [X] T029 [P] Unit test food pickers at `tests/python/unit/test_food_picker.py` — given a list of ItemSlots, each picker returns the expected item; ties broken deterministically.

**Checkpoint**: Foundation ready. Pathfinder, physics, chunk decoder, entity metadata, window-click, food, slots, events, errors — all unit-tested. User-story implementation can begin.

---

## Phase 3: US1 — Walk to coordinate (Priority: P1) 🎯 MVP

**Goal**: `await bot.walk_to(x, y, z)` autonomously navigates the bot via A* + physics tick. Bot climbs ledges, opens doors, swims, jumps gaps.

**Independent Test**: `python tools/quickstart_us1.py` succeeds against the live server — bot arrives within 1 block of a target 50 blocks away over mixed terrain within 60 s.

### World cache (subset needed for walk_to)

- [ ] T030 [US1] Implement `python/minecraft_bot/world/cache.py` — `World` class with `chunks` dict, `min_y`/`height`, `dimension_name`. Implements `get_block(x, y, z)`, `get_block_name`, `is_solid`, `is_navigable`, `is_water`. Subscribes via Bot to `map_chunk` → decode + insert, `block_change` → single update, `multi_block_change` → batch update, `unload_chunk` → drop entry, `respawn` → reset cache, `tile_entity_data` → update block-entity NBT.
- [ ] T031 [P] [US1] Unit test world cache at `tests/python/unit/test_world_cache.py` — load synthetic chunk, query blocks, apply block_change, verify update; apply unload_chunk, verify get_block returns None.

### Bot lifecycle + walk_to

- [ ] T032 [US1] Implement `python/minecraft_bot/bot.py` — `Bot` class: `__init__(connection)`, `offline()` classmethod (creates Connection + Bot), `connect()` (waits Connection.connect, then spawns physics tick), `disconnect()` (cancel tick, close Connection), `__aenter__`/`__aexit__`. Read-only properties: position, yaw, pitch, health, food, saturation, game_mode, is_dead, xp_level, xp_total, held_slot, held_item, entity_id, world_name, is_connected. Owns slot locks (movement/action/container).
- [ ] T033 [US1] Wire Bot to subscribe to Connection clientbound packets that derive state: position from `synchronize_player_position` + per-tick local prediction; health/food from `update_health`; xp from `experience`; game_mode from `login`/`game_state_change`; held_slot from `held_item_slot`; entity_id from `login`; world_name from `login`/`respawn`.
- [ ] T034 [US1] Implement `Bot.walk_to(x, y, z, timeout, max_fall, wait_for_slot)` — acquire movement slot; build a `World` view; run A*; drive physics tick per waypoint until within 1 block of target or timeout. Auto-open obstacles (doors/gates/trapdoors) when crossing. Re-path if a new chunk loads or a key block changes.
- [ ] T035 [US1] Implement physics auto-ticker — `_tick_task` spawned by `connect()`, runs `await self.tick()` every 50 ms best-effort. Cancelled by `disconnect()`. Server's `synchronize_player_position` resets PhysicsState before next tick (via existing Connection auto-confirm in 001's decode loop).
- [ ] T036 [US1] Implement `Bot.tick()` public method — exposes a single physics step for deterministic offline use (FR-010 / FR-133). Uses the same `physics.tick()` pure function as the auto-ticker.
- [ ] T037 [US1] Implement supporting movement methods: `look_at`, `look_by_vector`, `jump`, `sneak(True/False)`, `sprint(True/False)` (action slot). Each sends the appropriate serverbound packet via Connection.send (already FIFO-locked in 001).
- [ ] T038 [US1] Implement event-hook registry on Bot — `@bot.on(EventType)`, `bot.subscribe`, `bot.unsubscribe`, `bot.drain_events`, `bot.next_event`. Subscribe Bot's internal handlers to Connection's `on` to route packets → events.
- [ ] T039 [US1] Wire `Reconnected` event from Connection (already exists in 001) so it appears in `bot.drain_events()`.

### Tests

- [ ] T040 [P] [US1] Unit test Bot construction at `tests/python/unit/test_bot_construction.py` — `Bot.offline()` factory; properties default to None before connect; methods raise `ConnectionClosed` if not connected.
- [ ] T041 [P] [US1] Unit test walk_to with synthetic World at `tests/python/unit/test_walk_to_offline.py` — build a tiny synthetic World, mock Connection.send to capture position packets, call `walk_to`, verify the bot's local position evolves toward the target.
- [ ] T042 [US1] Integration test `tests/python/integration/test_us1_walk_to.py` (live): bot connects, calls `walk_to(spawn.x + 30, spawn.y, spawn.z + 30)`, asserts arrives within 60 s. Throttle-aware. Also includes a "no path" assertion against a walled target.

**Checkpoint**: US1 complete — bot autonomously walks. **MVP achieved.**

---

## Phase 4: US2 — Observe world and entities (Priority: P1)

**Goal**: bot exposes `bot.world.find_blocks_nearby(...)`, `bot.entities.nearby_entities(...)`, full typed metadata per ~50 entity types.

**Independent Test**: `python tools/quickstart_us2.py` — bot prints nearby oak_logs and sheep with `wool_color` typed accessor within seconds of joining.

### World cache full surface

- [ ] T043 [US2] Extend `python/minecraft_bot/world/cache.py` — implement `find_blocks_nearby(name, radius, limit) -> list[(x, y, z)]` with chunk-by-chunk scan; sort ascending by distance to bot; respect `limit`.
- [ ] T044 [P] [US2] Unit test `find_blocks_nearby` at `tests/python/unit/test_world_cache.py` (extends T031) — synthetic World with multiple matching blocks, assert sorted-by-distance correctness and limit truncation.

### Entity tracker + metadata application

- [ ] T045 [US2] Implement `python/minecraft_bot/entities/tracker.py` — `EntityTracker` class with `_entities: dict[int, Entity]`. Public methods `nearby_entities(radius, type_filter)`, `nearby_players(radius)`, `find_by_id(id)`, `distance_to(eid)`. Subscribes to `spawn_entity` / `named_entity_spawn` / `spawn_entity_experience_orb` (construct appropriate subclass via type-id), `entity_metadata` (decode stream + update metadata + re-apply typed accessors), `rel_entity_move`/`entity_move_look`/`entity_teleport` (position update with fixed-point unpacking), `entity_velocity`, `entity_head_rotation`, `entity_destroy`, `entity_status`, `update_entity_attributes` (per-attribute store).
- [ ] T046 [US2] Generate ~50 entity subclasses via `tools/generate_entity_subclasses.py --version v763` — produces files under `python/minecraft_bot/entities/types/{snake_name}.py`. Each has `ENTITY_TYPE_ID`, inheritance from appropriate base (Mob / Animal / Hostile / Vehicle / Item / Projectile), typed `@property` accessors for every metadata index in `entity_metadata.json`.
- [ ] T047 [US2] Hand-tune the generated entity subclasses — fix docstrings, add convenience helpers (e.g., `wolf.owner_uuid` → resolved name via tab list), add type unions for `OptUUID`/`OptVarInt`. Mark hand-edits with explicit `# manual edit` blocks so codegen doesn't overwrite.
- [ ] T048 [US2] Implement `python/minecraft_bot/entities/types/__init__.py` — type-id → subclass lookup `lookup_class(type_id) -> type[Entity]`. Defaults to base `Mob` / `Entity` / `Player` if type-id unrecognised (e.g., modded entities) so the tracker never crashes.
- [ ] T049 [P] [US2] Unit test entity tracker at `tests/python/unit/test_entity_tracker.py` — synthetic `spawn_entity` for sheep → returned object is `Sheep` instance with `wool_color` accessor; `rel_entity_move` updates position; `entity_destroy` removes entity.
- [ ] T050 [P] [US2] Lint test entity subclass shape at `tests/python/unit/test_entity_subclass_shape.py` — every entity-type-id in `entity_metadata.json` has a corresponding Python class with every declared metadata index exposed as a property.

### Attack + interact

- [ ] T051 [US2] Implement `Bot.attack(eid)`, `Bot.interact_entity(eid)`, `Bot.swing_arm(hand=0)`, `Bot.use_item(hand=0)` (all action slot). Each sends the appropriate `use_entity` / `arm_animation` / `use_item` packet via Connection.send. attack also swings arm automatically.

### Tests

- [ ] T052 [US2] Integration test `tests/python/integration/test_us2_world_entities.py` (live): bot connects, waits 5 s for chunks, asserts `find_blocks_nearby("dirt", radius=16, limit=10)` returns > 0; asserts `nearby_entities(radius=64)` is non-empty; asserts at least one Sheep has typed `wool_color` if any sheep around.

**Checkpoint**: US2 complete — bot observes world + entities with typed access.

---

## Phase 5: US3 — Inventory + containers (Priority: P1)

**Goal**: bot reads inventory, equips armor, opens chests, crafts, smelts.

**Independent Test**: `python tools/quickstart_us3.py` — bot gets diamond sword via `/give`, walks to a chest, opens it, prints contents.

### ItemSlot + NBT helpers

- [ ] T053 [US3] Implement `python/minecraft_bot/inventory/item.py` — `ItemSlot` frozen dataclass (item_id, count, name, nbt). Lazy parsed properties: `damage` (from NBT `Damage`), `enchantments` (list of `Enchantment(id, level)` from NBT `Enchantments`), `display_name` (from NBT `display.Name` JSON), `custom_model_data`, `is_unbreakable`. `Enchantment` is its own small frozen dataclass.
- [ ] T054 [P] [US3] Unit test ItemSlot NBT helpers at `tests/python/unit/test_item_slot.py` — diamond pickaxe with `Damage:5` → `damage == 5`; sword with Enchantments list → `enchantments == [Enchantment("minecraft:sharpness", 5)]`; item with no display.Name → `display_name is None`.

### Inventory tracker

- [ ] T055 [US3] Implement `python/minecraft_bot/inventory/tracker.py` — `InventoryTracker` class with `player_slots: list[Optional[ItemSlot]]` (46 slots), `container_window_id`, `container_type`, `container_slots`, `cursor`, `state_id`. Subscribes to `set_slot` (single slot update), `window_items` (bulk), `open_screen` (set container_window_id), `close_window` (clear container).
- [ ] T056 [US3] Public InventoryTracker methods per FR-060…FR-070: `items()`, `hotbar_items()`, `container_items()`, `find_item(name)`, `count_item(name)`. Then async methods via window helper (T026): `click_slot`, `move_item`, `drop_item`, `equip_armor`, `unequip_armor`, `swap_to_offhand`. Each uses `Connection.send` for the underlying packet.
- [ ] T057 [US3] Implement `Bot.select_slot(0..8)` (action slot) — sends `held_item_slot` serverbound; updates Bot's `held_slot` property on server ack (the serverbound `held_item_slot` doesn't return ack — we trust our own value optimistically and watch for server `set_slot` if it diverges).

### Containers

- [ ] T058 [US3] Implement `Bot.open_chest(x, y, z)`, `open_furnace(x, y, z)`, `open_crafting_table(x, y, z)` (container slot) — each sends `block_place` (right-click), awaits clientbound `open_screen` + first `window_items`, returns a `Container` handle (thin wrapper exposing `items()`).
- [ ] T059 [US3] Implement `Bot.close_container()` — sends `close_window` serverbound; clears `InventoryTracker.container_*`.
- [ ] T060 [US3] Implement `Bot.craft(recipe, x, y, z)` via RMB+scan pattern (R-06) — opens crafting table, places ingredients into slots 1-9, polls `window_items` for result in slot 0, shift-clicks to collect.
- [ ] T061 [US3] Implement `Bot.smelt(input_item, fuel_item, x, y, z)` via similar pattern — places fuel slot 1, input slot 0, polls slot 2 for output.

### Tests

- [ ] T062 [P] [US3] Unit test InventoryTracker state evolution at `tests/python/unit/test_inventory_tracker.py` — apply `window_items` → items() returns those; `set_slot` updates single; `open_screen` populates container; `close_window` clears.
- [ ] T063 [US3] Integration test `tests/python/integration/test_us3_inventory.py` (live, op-mode): bot uses `/give` to get a stack of items, asserts `find_item` works, opens a placed chest, asserts container_items reads its content; uses move_item to transfer one stack and asserts result on server side via another window_items.

**Checkpoint**: US3 complete — full inventory + container mastery.

---

## Phase 6: US4 — Survive autonomously (Priority: P2)

**Goal**: bot survives in survival mode with auto_eat, dig with break-time, attack hostiles, react to status effects.

**Independent Test**: `python tools/quickstart_us4.py` — bot in survival eats from inventory when hungry, kills a nearby zombie.

### Status effects

- [ ] T064 [US4] Implement `python/minecraft_bot/status_effects.py` — `StatusEffects` class with `effects: dict[str, EffectEntry]`. `EffectEntry` is a frozen dataclass with `id, amplifier, duration_ticks, is_ambient, show_particles, show_icon`. Subscribes to `entity_effect` (add/update if target is bot's entity_id) and `remove_entity_effect` (delete on match).
- [ ] T065 [P] [US4] Unit test status effects at `tests/python/unit/test_status_effects.py` — apply effect, has_effect=True; remove, has_effect=False; amplifier+duration parsed correctly.

### Auto-eat

- [ ] T066 [US4] Implement `Bot.auto_eat(threshold=15, eat_duration=1.6, picker=None)` — registers a periodic check (every 5 ticks = 250 ms). When `bot.food < threshold` and inventory has any food, runs the picker (default `BEST_SATURATION`), `select_slot(slot)`, `use_item(hand=0)`, waits eat_duration, returns. Acquires action slot during the eat.
- [ ] T067 [P] [US4] Unit test auto-eat picker integration at `tests/python/unit/test_auto_eat.py` — synthetic Bot with low food + mock inventory containing bread/golden_apple/rotten_flesh; picker chooses correctly per policy; with `picker=WORST_FIRST` chooses rotten_flesh.

### Dig with break-time

- [ ] T068 [US4] Implement `Bot.dig(x, y, z, tool=None)` (movement slot) — sends `block_dig` status=0 (start), waits the natural break-time for the block + held tool (computed from block name + tool effectiveness table loaded from minecraft-data), sends status=2 (finish). Times out at 2× natural break-time → `DigFailed`.
- [ ] T069 [P] [US4] Unit test break-time calculation at `tests/python/unit/test_break_time.py` — known block+tool combinations match wiki values within ±5%: dirt by hand ~750 ms; stone by wooden_pickaxe ~1500 ms; stone by hand >7500 ms.

### Tests

- [ ] T070 [US4] Integration test `tests/python/integration/test_us4_survive.py` (live, survival mode): bot enabled with `auto_eat`, gives itself cooked_beef via /give, `/gamemode survival`, takes damage from `/damage`, asserts food restored within 5 s. Attacks a `/summon zombie`, asserts zombie's health drops over time. Diggs a placed dirt block, asserts it's gone via `bot.world.get_block`.

**Checkpoint**: US4 complete — bot survives.

---

## Phase 7: US5 — Follow an entity (Priority: P2)

**Goal**: `Bot.follow(eid)` tracks a moving target.

**Independent Test**: `python tools/quickstart_us5.py` — bot follows another connected player around spawn for 60 s, stays within 4 blocks.

- [ ] T071 [US5] Implement `Bot.follow(eid, distance, timeout, wait_for_slot)` (movement slot) — periodically re-paths with A* to a position `distance` blocks from the target's current location; restarts walk_to whenever target moves more than 2 blocks. Raises `TargetLost` if entity vanishes; `WalkTimeout` if elapsed.
- [ ] T072 [P] [US5] Unit test follow re-path trigger at `tests/python/unit/test_follow.py` — mock target that moves; assert follow issues a new walk_to after the target moves > 2 blocks.
- [ ] T073 [US5] Integration test `tests/python/integration/test_us5_follow.py` (live): bot connects, looks for any other nearby player (skip with informative message if none); `follow(player_id, distance=3, timeout=60)`; asserts distance to target stays ≤ 4 blocks throughout (sampled every 2 s).

**Checkpoint**: US5 complete.

---

## Phase 8: US6 — Behaviour trees (Priority: P3)

**Goal**: developers compose bot behaviour from BT nodes.

**Independent Test**: `python tools/quickstart_us6.py` — a 3-branch tree (eat / attack / walk-to-spawn) runs for 5 minutes and bot behaves per policy.

- [ ] T074 [US6] Implement `python/minecraft_bot/behaviour/nodes.py` — `NodeStatus` enum (Success/Failure/Running), `BehaviourNode` abstract base, `Selector`, `Sequence`, `Inverter`, `RepeatUntilFail`, `AlwaysSucceed`, `Condition(predicate)`, `Action(coroutine_factory)`. Each `async tick(bot, ctx) -> NodeStatus`. `BehaviourRunner` loops on the root node.
- [ ] T075 [US6] Implement `python/minecraft_bot/behaviour/actions.py` — built-in primitives: `WalkTo(x, y, z)`, `AttackNearest(filter)`, `EatWhenHungry(threshold)`, `FollowPlayer(name)`, `DropItem(slot)`, `Say(message)`. Each wraps the corresponding Bot method.
- [ ] T076 [US6] Add `Bot.behaviour` attribute — a `BehaviourRunner` instance; `await bot.behaviour.run(tree, max_iterations=None)`.
- [ ] T077 [P] [US6] Unit test BT nodes at `tests/python/unit/test_behaviour_nodes.py` — Selector returns Success on first child Success; Sequence on all-Success; Failure short-circuits; Inverter flips. Mock bot for Action.
- [ ] T078 [US6] Integration test `tests/python/integration/test_us6_behaviour.py` (live): build a tree "eat if hungry else walk back to spawn"; run for 2 minutes; assert bot's position oscillates near spawn (it walks back when displaced).

**Checkpoint**: US6 complete.

---

## Phase 9: US7 — Chat & commands (Priority: P3)

**Goal**: bot sends chat / slash-commands; ChatMessageEvent fires for incoming chat.

**Independent Test**: `python tools/quickstart_us7.py` — bot says "ChatBot online"; other player types "!ping" → bot replies "pong @<name>".

- [ ] T079 [US7] Implement `Bot.say(message)`, `Bot.command(slash_command)` (action slot) — wrap `chat_message` / `chat_command` serverbound packets with the framework's default timestamp / salt / empty signature / state_id.
- [ ] T080 [US7] Wire `player_chat` / `profileless_chat` / `system_chat` clientbound packets → `ChatMessageEvent` with parsed sender + message text.
- [ ] T081 [P] [US7] Unit test say/command at `tests/python/unit/test_chat.py` — mock Connection.send; assert say emits chat_message with given content + timestamp > 0.
- [ ] T082 [US7] Integration test `tests/python/integration/test_us7_chat.py` (live): bot says unique message; asserts the next `system_chat`/`player_chat` event from server confirms broadcast.

**Checkpoint**: US7 complete; all 7 user stories done.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: SC verification, lints, docs.

- [ ] T083 [P] Performance test `tests/python/perf/test_tick_latency.py` — `pytest-benchmark` on `bot.tick()` median ≤ 5 ms, p99 ≤ 25 ms (SC-009).
- [ ] T084 [P] Performance test `tests/python/perf/test_find_blocks.py` — `find_blocks_nearby("oak_log", radius=32, limit=5)` runs in < 100 ms on a synthetic World preloaded with ≥ 5 oak_log positions (SC-008).
- [ ] T085 [P] Performance test `tests/python/perf/test_behaviour_eval.py` — 10-node tree of depth 4 evaluates in < 1 ms median (SC-010).
- [ ] T086 [P] Lint entity subclass coverage at `tests/python/unit/test_entity_subclass_shape.py` (extends T050 if needed) — assert there's no entity-type-id from `entity_metadata.json` missing a Python class.
- [ ] T087 [P] Zero-deps lint runs on new files (extends 001's `tests/python/unit/test_zero_deps.py`; nothing to add since the existing test walks all `.py` files under `python/minecraft_bot/`).
- [ ] T088 [P] BotSnapshot implementation at `python/minecraft_bot/bot.py` — `Bot.snapshot() -> BotSnapshot` frozen dataclass with position, yaw, pitch, health, food, saturation, inventory tuple, nearby_entities tuple, status_effects tuple. Used for ML observation pipelines.
- [ ] T089 [P] Update `README.md` at repo root — note the Bot API milestone, add `pip install -e python/[dev]` plus a 5-line "hello bot" example.
- [ ] T090 Run `quickstart.md` end-to-end on a clean checkout — all 7 quickstart scripts succeed against a live server.
- [ ] T091 [P] CI matrix update — extend `.github/workflows/ci.yml` (added in 001) to include the new test files in default + live runs.
- [ ] T092 [P] Long-uptime live test `tests/python/integration/test_sc006_survive_10min.py` (live, slow) — bot in survival mode with auto_eat runs for 10 min idle near spawn; assert is_connected throughout and no death.

**Checkpoint**: All 12 success criteria measured; constitution re-verified.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no prerequisites within 002. Depends on 001 being merged into the branch base.
- **Phase 2 (Foundational)**: depends on Phase 1. **BLOCKS all user stories.** Slot model, block table, chunk decoder, A*, physics, entity metadata, window-click, food, events, errors — required by every US.
- **Phase 3 (US1)**: depends on Phase 2. MVP-eligible. Independently demonstrable.
- **Phase 4 (US2)**: depends on Phase 2 + parts of US1 (Bot lifecycle, World cache base). May land sequentially after US1 to keep the dependency chain linear; could be parallel if World cache is split into two phases.
- **Phase 5 (US3)**: depends on Phase 2 (window-click helper, ItemSlot already foundational) + US1 (Bot lifecycle).
- **Phase 6 (US4)**: depends on US1 (movement), US2 (entity tracker), US3 (inventory + use_item).
- **Phase 7 (US5)**: depends on US1 (walk_to) + US2 (entity tracker).
- **Phase 8 (US6)**: depends on all previous user stories (BT primitives wrap them).
- **Phase 9 (US7)**: depends on Phase 2 (events) + US1 (Bot lifecycle). Independent of US2-US6.
- **Phase 10 (Polish)**: depends on all previous phases.

### Within Each User Story

- Foundational entities + helpers land before the public methods that use them.
- Public method implementation lands before its tests (offline unit tests, then live integration tests).
- Live integration test is the LAST task of each user-story phase.

### Parallel Opportunities

- All [P]-marked unit tests run truly in parallel — they touch distinct files.
- Phase 2's 10 implementation chunks (T010-T029) split into 4-5 parallel tracks: slot/events/errors, block-table, chunk decoder, A*, physics, entity metadata, window-click, food.
- Phase 4's ~50 entity subclasses are codegen'd in one task (T046) then hand-tuned in one task (T047) — internally parallel since each file is independent.
- Phase 10's polish tasks are heavily [P].

---

## Parallel Example: Phase 2 Foundational

```bash
# Once Phase 1 setup is complete, kick off the foundational implementations:
Task: "Implement slots.py with BotBusy and 3-lock model"   # T010
Task: "Implement events.py with 13 event types"             # T012
Task: "Extend errors.py with 7 new exceptions"              # T013
Task: "Implement block_table.py loading block_states.json"  # T014
Task: "Implement chunk.py PalettedContainer + ChunkSection" # T016
Task: "Implement pathfinding.py 8-dir A*"                   # T019
Task: "Implement physics.py 20-Hz tick pure function"       # T021
Task: "Implement entities/metadata.py stream codec"         # T023
Task: "Implement inventory/window.py click helper"          # T026
Task: "Implement inventory/food.py + pickers"               # T028
# All 10 above are independent files → parallel.
# Tests T011/T015/T018/T020/T022/T024/T027/T029 follow each impl in parallel.
```

## Parallel Example: US2 entity subclasses

```bash
# After codegen (T046) produces ~50 files, hand-tuning (T047) is parallel-friendly:
# Each entity file is independent — one developer per ~10 entities works fine.
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Phase 1 (Setup): T001-T009. ~half a day.
2. Phase 2 (Foundational): T010-T029. Multi-day; ~10 components × test each.
3. Phase 3 (US1): T030-T042. Multi-day; live-server smoke at the end.
4. **STOP and VALIDATE**: `python tools/quickstart_us1.py` succeeds. **MVP shipped.**
5. The bot can walk autonomously. Other behaviours (US2-US7) build on the same Bot + Connection + slot model.

### Incremental Delivery

After MVP:

- **Cycle 2**: US2 (Phase 4) → world cache full + entity tracker + ~50 subclasses.
- **Cycle 3**: US3 (Phase 5) → inventory + containers + crafting.
- **Cycle 4**: US4 (Phase 6) → survive (auto_eat + dig + attack + effects).
- **Cycle 5**: US5 (Phase 7) → follow.
- **Cycle 6**: US6 (Phase 8) → behaviour trees.
- **Cycle 7**: US7 (Phase 9) → chat + commands.
- **Cycle 8**: Phase 10 → SC verification, polish, docs.

### Parallel Team Strategy

After Phase 2 completes, US1-US4 can proceed in parallel if staffed:

- **Dev A**: US1 (Bot lifecycle + walk_to)
- **Dev B**: US2 (entity tracker + ~50 subclasses) — biggest chunk
- **Dev C**: US3 (inventory + containers + craft/smelt)
- **Dev D**: US4 (status effects + auto_eat + dig)
- **Dev E**: US7 (chat + commands) — small and parallelisable

US5/US6 wait on US1+US2; Polish waits on all.

---

## Notes

- [P] = different files, no incomplete dependencies. Verify before parallelising.
- [Story] label maps tasks to user story for traceability.
- Each user-story phase ends with a live-server integration test (FR-141).
- Entity subclasses are scaffolded by codegen then hand-tuned (R-04 / R-10).
- The data tables `protocol-data/v763/*.json` are pinned snapshots; refresh policy documented in `protocol-data/v763/README.md` (extended in T006).
- Commit per task or per logical group. Stop at any "Checkpoint" to validate.

---

## Task count summary

| Phase | Tasks | Notes |
|---|---|---|
| 1. Setup | 9 (T001-T009) | Data fetches + dir scaffolding |
| 2. Foundational | 20 (T010-T029) | Slot/events/errors + block table + chunk decoder + A* + physics + entity metadata + window-click + food (each impl + test) |
| 3. US1 (walk_to) | 13 (T030-T042) | World cache base + Bot lifecycle + walk_to + supporting methods + tests |
| 4. US2 (observe) | 10 (T043-T052) | find_blocks_nearby + entity tracker + ~50 subclasses (codegen + hand-tune) + attack |
| 5. US3 (inventory) | 11 (T053-T063) | ItemSlot + InventoryTracker + containers + craft + smelt |
| 6. US4 (survive) | 7 (T064-T070) | Effects + auto_eat + dig |
| 7. US5 (follow) | 3 (T071-T073) | |
| 8. US6 (BT) | 5 (T074-T078) | |
| 9. US7 (chat) | 4 (T079-T082) | |
| 10. Polish | 10 (T083-T092) | SC verification + lints + docs + long uptime |
| **Total** | **92 tasks** | |

**Parallel-marked tasks**: ~45 of 92 (~49%) carry the `[P]` flag.

**Independent test criteria recap**:

- US1: `quickstart_us1.py` arrives at target within 60 s on live server.
- US2: `find_blocks_nearby("oak_log", 32, 5)` and `nearby_entities(64)` non-empty; sheep has typed `wool_color`.
- US3: open chest, read items, move_item; visible in-game.
- US4: bot survives 10 min idle in survival mode with auto_eat enabled.
- US5: follow another player for 60 s, distance stays ≤ 4 blocks.
- US6: 3-branch tree runs 5 minutes, behaviour matches policy.
- US7: `bot.say(msg)` visible to other players within 200 ms.

**Suggested MVP scope**: Phases 1 + 2 + 3 (T001-T042). Delivers an autonomous walker. Sufficient to unblock all subsequent stories.
