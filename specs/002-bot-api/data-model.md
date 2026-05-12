# Phase 1 Data Model: Bot API

**Date**: 2026-05-12
**Plan**: [plan.md](./plan.md) · **Spec**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

This document captures the entities, fields, relationships, validation
rules, and state transitions that fall out of the spec. It is the
normative model for the Python implementation; a future Rust mirror
will reproduce these shapes field-for-field.

Each entity is listed with: **Purpose · Fields · Relationships ·
Validation · Lifecycle · File location**.

---

## E-1 `Bot`

**Purpose**: the developer-facing handle. Owns a `Connection` from
001, four trackers (World, EntityTracker, InventoryTracker,
StatusEffects), the physics tick, the slot model, and an event-hook
registry.

**Fields**:
- `connection: Connection` — public attribute, the underlying 001 wire link
- `world: World` — voxel cache
- `entities: EntityTracker` — entity tracker
- `inventory: InventoryTracker` — player + open-container inventory
- `status_effects: StatusEffects` — active potion effects
- `behaviour: BehaviourRunner | None` — optional BT runtime
- Read-only properties (derived from packets):
  - `position: tuple[float, float, float]` — `(x, y, z)`
  - `yaw: float`, `pitch: float`
  - `health: float` (0..20), `food: int` (0..20), `saturation: float`
  - `game_mode: int` (0=survival, 1=creative, 2=adventure, 3=spectator)
  - `is_dead: bool`
  - `xp_level: int`, `xp_total: int`
  - `held_slot: int` (0..8 hotbar index)
  - `held_item: ItemSlot | None`
- Internal:
  - `_movement_slot: asyncio.Lock`
  - `_action_slot: asyncio.Lock`
  - `_container_slot: asyncio.Lock`
  - `_handlers: dict[type[Event], list[Callable]]`
  - `_tick_task: asyncio.Task | None`

**Relationships**: composes Connection (from 001) + four trackers +
slot model + handler registry.

**Validation**: must be constructed on a `Connection` that is in
PLAY state. `Bot.connect()` waits for PLAY then spawns the physics
tick.

**Lifecycle**:
```text
construct (with Connection)
  -> Bot.connect()        # ensure PLAY, start physics tick
  -> [running]            # ticks running, methods callable
  -> Bot.disconnect()     # cancel tick, close Connection
  -> [closed]
```

On dimension change (`respawn` packet with new dimension): all
trackers reset; the physics tick continues.

On `Reconnected` event (auto_reconnect=True): all trackers reset.

**File location**: `python/minecraft_bot/bot.py`.

---

## E-2 `World`

**Purpose**: voxel cache. Maps chunk coordinates → loaded chunk data;
serves block-level queries.

**Fields**:
- `chunks: dict[tuple[int, int], Chunk]` — `{(chunk_x, chunk_z): Chunk}`
- `min_y: int` (default -64 for overworld), `height: int` (default 384)
- `dimension_name: str | None`

**Public API** (per FR-040…FR-046):
- `get_block(x, y, z) -> int | None` — block-state ID or None if chunk unloaded
- `get_block_name(x, y, z) -> str | None`
- `is_solid(x, y, z) -> bool`, `is_navigable(x, y, z) -> bool`, `is_water(x, y, z) -> bool`
- `find_blocks_nearby(name, radius, limit) -> list[tuple[int, int, int]]`

**Update events** (received via packet subscription):
- `block_change` → set single block
- `multi_block_change` → set N blocks in a chunk section
- `map_chunk` → load full chunk via `decode_chunk`
- `unload_chunk` → drop chunk from `chunks` (server-driven eviction, FR-046)
- `respawn` → clear cache on dimension change
- `tile_entity_data` → update block-entity NBT on referenced position

**File location**: `python/minecraft_bot/world/cache.py`.

---

## E-3 `Chunk`

**Purpose**: a single 16×N×16 chunk's block storage.

**Fields**:
- `cx: int`, `cz: int` (chunk coordinates)
- `sections: list[ChunkSection]` — one per 16-block vertical slice (24 in overworld)
- `biomes: list[PalettedContainer]` — 4×4×4 biome cells per section
- `block_entities: dict[tuple[int, int, int], BlockEntityRecord]`
- `heightmaps: dict[str, list[int]]` — long-packed heightmaps from NBT

**Queries**: `chunk.get_block(local_x, y, local_z) -> int`.

**File location**: `python/minecraft_bot/world/chunk.py`.

---

## E-4 `ChunkSection`

**Purpose**: 16×16×16 block-state container.

**Fields**:
- `block_count: int` — non-air count (for "section empty" optimisation)
- `block_states: PalettedContainer`
- `biomes: PalettedContainer`

**File location**: `python/minecraft_bot/world/chunk.py`.

---

## E-5 `PalettedContainer`

**Purpose**: the wire format for per-section block / biome data —
either a direct array, a paletted indexed array, or a single value
(when the section is uniform).

**Fields**:
- `bits_per_entry: int`
- `palette: list[int] | None` — None for direct mode
- `data: array.array('Q', ...)` — long-packed indices
- `single_value: int | None` — set when section is uniform

**File location**: `python/minecraft_bot/world/chunk.py`.

---

## E-6 `Entity` (base class + ~50 typed subclasses)

**Purpose**: tracked entity record. Concrete subtype per
entity-type-id (FR-053).

**Common fields** (Entity base):
- `id: int` — entity id
- `uuid: UUID | None` — present for player + most mobs
- `type: int` — entity-type registry id
- `position: tuple[float, float, float]`
- `yaw: float`, `pitch: float`, `head_yaw: float`
- `velocity: tuple[float, float, float]`
- `metadata: dict[int, Any]` — raw stream-decoded metadata
- `on_ground: bool`

**Living fields** (Living : Entity):
- `health: float`
- `is_baby: bool`
- `pose: int`
- `custom_name: str | None`
- `custom_name_visible: bool`

**Mob fields** (Mob : Living): equipment, AI state.

**Player fields** (Player : Living): skin_parts, cape, score.

**Per-type subclasses** (~50, e.g.):
- `Sheep(Animal)` — wool_color, is_sheared
- `Wolf(TameableAnimal)` — collar_color, tame_status, sit_status
- `Horse(AbstractHorse)` — variant, armor, owner
- `Villager(Mob)` — profession, level, biome_id
- `Creeper(Mob)` — state, is_charged, is_ignited
- `ItemEntity(Entity)` — item: ItemSlot
- … (one file per type, see R-04)

**File location**: `python/minecraft_bot/entities/base.py` for base
classes; `python/minecraft_bot/entities/types/{snake_case_name}.py` for
each concrete subclass.

---

## E-7 `EntityTracker`

**Purpose**: maintains the `{id: Entity}` mapping.

**Public API**:
- `nearby_entities(radius, type_filter=None) -> list[Entity]`
- `nearby_players(radius) -> list[Player]`
- `find_by_id(id) -> Entity | None`
- `distance_to(eid) -> float | None`

**Update events**:
- `spawn_entity` → construct subclass via type-id, add to map
- `named_entity_spawn` → construct Player, add
- `entity_metadata` → decode stream, update `entity.metadata` and re-typed accessors
- `rel_entity_move` / `entity_move_look` / `entity_teleport` →
  update position (with fixed-point unpacking for delta moves)
- `entity_velocity` → update velocity
- `entity_destroy` → remove from map
- `entity_status` → update transient state flag
- `update_entity_attributes` → update attributes (health max, speed)

**File location**: `python/minecraft_bot/entities/tracker.py`.

---

## E-8 `InventoryTracker`

**Purpose**: player inventory + active container window.

**Fields**:
- `player_slots: list[ItemSlot | None]` — 46 slots (crafting grid 0-4, armor 5-8, hotbar 36-44, offhand 45, main 9-35)
- `container_window_id: int | None`
- `container_type: int | None` (registry id)
- `container_slots: list[ItemSlot | None]` — empty unless container open
- `cursor: ItemSlot | None` — drag-and-drop cursor
- `state_id: int` — most recent server state_id from `set_slot`/`window_items`

**Public API** (FR-060…FR-070):
- `items()`, `hotbar_items()`, `container_items()`
- `select_slot(0..8)`, `click_slot(...)`, `move_item(from, to)`, `drop_item(...)`
- `find_item(name)`, `count_item(name)`
- `equip_armor(name)`, `unequip_armor(slot)`, `swap_to_offhand(slot)`

**Update events**:
- `set_slot` → update single slot
- `window_items` → bulk update all slots
- `open_screen` → set container_window_id and container_type
- `close_window` → clear container_window_id and container_slots
- Player respawn → reset to empty inventory

**File location**: `python/minecraft_bot/inventory/tracker.py`.

---

## E-9 `ItemSlot`

**Purpose**: one populated inventory slot with parsed NBT helpers
(FR-068).

**Fields** (frozen dataclass):
- `item_id: int` — registry id
- `count: int`
- `name: str` — resolved namespace:path (e.g., "minecraft:diamond_pickaxe")
- `nbt: NbtTag | None` — raw NBT for caller-side custom parsing

**Computed properties** (parsed from NBT on demand):
- `damage: int` — from NBT `Damage` tag (0 = undamaged)
- `enchantments: list[Enchantment]` — list of `(id, level)`
- `display_name: str | None` — from NBT `display.Name` JSON
- `custom_model_data: int | None`
- `is_unbreakable: bool`

**File location**: `python/minecraft_bot/inventory/item.py`.

---

## E-10 `Enchantment`

**Purpose**: parsed enchantment entry within an item's NBT.

**Fields** (frozen dataclass):
- `id: str` — enchantment registry id (e.g., "minecraft:sharpness")
- `level: int`

**File location**: `python/minecraft_bot/inventory/item.py`.

---

## E-11 `StatusEffects`

**Purpose**: active potion effects on the bot.

**Fields**:
- `effects: dict[str, EffectEntry]` — keyed by effect identifier

**Public API**:
- `has_effect(name) -> bool`
- `get_effect(name) -> EffectEntry | None`

**Update events**:
- `entity_effect` → add/update if target is bot's entity_id
- `remove_entity_effect` → delete if target matches

**File location**: `python/minecraft_bot/status_effects.py`.

---

## E-12 `EffectEntry`

**Purpose**: one active potion effect.

**Fields** (frozen dataclass):
- `id: str` — registry id
- `amplifier: int` — 0..255
- `duration_ticks: int` — remaining duration
- `is_ambient: bool`
- `show_particles: bool`
- `show_icon: bool`

**File location**: `python/minecraft_bot/status_effects.py`.

---

## E-13 `PhysicsState`

**Purpose**: per-tick simulation state for the bot.

**Fields** (per-tick, replaced each tick):
- `position: tuple[float, float, float]`
- `velocity: tuple[float, float, float]`
- `on_ground: bool`
- `in_water: bool`
- `in_lava: bool`
- `is_sneaking: bool`, `is_sprinting: bool`
- `last_jump_tick: int`
- `blocked_x: bool`, `blocked_z: bool`

**Lifecycle**: produced fresh by each physics tick from previous
state + inputs + world; never persisted across server-sync resets.

**File location**: `python/minecraft_bot/physics.py`.

---

## E-14 `Path`

**Purpose**: A* result — a sequence of waypoints.

**Fields** (frozen dataclass):
- `nodes: list[tuple[int, int, int]]` — waypoint sequence
- `cost: float` — total g-score
- `nodes_explored: int` — A* nodes visited (for debug)

**Methods**:
- `next_waypoint(current_pos) -> tuple[int, int, int] | None` — first waypoint not yet reached.

**File location**: `python/minecraft_bot/pathfinding.py`.

---

## E-15 `Event` (base + concrete subtypes — FR-101)

**Purpose**: hookable event signaling a state change.

**Concrete subtypes** (each a frozen dataclass):
- `ChatMessageEvent(sender, message, type)`
- `EntityDamageEvent(entity_id, damage, source_id)`
- `EntityDeathEvent(entity_id)`
- `ItemPickupEvent(slot, item)`
- `InventoryChangeEvent(slot, old, new)`
- `BlockBreakEvent(x, y, z, broken_by_entity_id)`
- `ContainerOpenEvent(window_id, type)`
- `ContainerCloseEvent(window_id)`
- `Reconnected(attempts, elapsed)` (re-exported from 001)
- `TeleportedEvent(old_position, new_position)`
- `InLavaEvent(position)`
- `DimensionChangedEvent(old, new)`
- `RespawnEvent()`

**File location**: `python/minecraft_bot/events.py`.

---

## E-16 `BehaviourNode` (base + concrete — FR-120…FR-122)

**Purpose**: composable BT node.

**Concrete subtypes**:
- `Selector(children)`
- `Sequence(children)`
- `Inverter(child)`
- `RepeatUntilFail(child)`
- `AlwaysSucceed(child)`
- `Condition(predicate)`
- `Action(coroutine_factory)`

**Built-in primitives**:
- `WalkTo(x, y, z)`, `AttackNearest(filter)`, `EatWhenHungry(threshold)`,
  `FollowPlayer(name)`, `DropItem(slot)`, `Say(message)`.

**Interface**:
- `async tick(bot, ctx) -> NodeStatus`
- `NodeStatus ∈ {Success, Failure, Running}`

**File location**: `python/minecraft_bot/behaviour/nodes.py`,
`python/minecraft_bot/behaviour/actions.py`.

---

## E-17 `BotBusy` (exception)

**Purpose**: raised when a slot is already held and `wait_for_slot=False`.

**File location**: `python/minecraft_bot/slots.py`.

---

## Cross-entity invariants

1. **3-slot concurrency** (FR-027): every long-running movement / dig
   method acquires the movement-slot lock; every instant-effect
   method acquires the action-slot lock; container interaction
   acquires the container-slot lock. The three locks compose freely;
   contending callers raise `BotBusy` unless `wait_for_slot=True`.

2. **World cache eviction is server-driven** (FR-046): the World class
   never evicts a chunk except on `unload_chunk`.

3. **Server-authoritative position** (FR-011): on every
   `SynchronizePlayerPosition`, `Bot.position` and `PhysicsState`
   reset to server values; the teleport-confirm auto-reply (already
   in 001) fires within the decode loop critical path.

4. **Multi-bot ready** (FR-131): no shared mutable globals; all state
   lives on the per-Bot trackers. The block-state and entity-metadata
   data tables are loaded once at import time and are read-only
   afterwards.

5. **PyO3 representability** (FR-134): every public class uses only
   types that PyO3 can cross — no raw pointers, no callbacks that
   can't be pickled, no `weakref` cycles on the API surface.

6. **Per-session reset on dimension change**: World, EntityTracker,
   InventoryTracker, and StatusEffects all clear on `respawn` with
   a new dimension. Subscribers receive `DimensionChangedEvent`
   first, then trackers reset.

7. **Inventory state_id discipline**: every `click_slot` includes
   the most recent `state_id` from the server; out-of-sync clicks
   raise (`InventoryStateMismatch`) so the developer doesn't silently
   miss an update.

---

## Summary

17 primary entities + per-entity-type subclasses (~50). All trace
back to a spec FR or constitution principle. Concurrency, eviction,
and reset semantics are formalised as cross-entity invariants. The
Bot class is the orchestrator; everything else is composable
substrate.
