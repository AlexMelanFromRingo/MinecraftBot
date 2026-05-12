# Feature Specification: Bot API

**Feature Branch**: `002-bot-api`
**Created**: 2026-05-12
**Status**: Draft
**Input**: User description: "Bot API — высокоуровневый интерфейс над протокольным фундаментом 001. Движение, физика, pathfinding, world cache, entity/inventory tracker, survival helpers, hooks, chat."

## Clarifications

### Session 2026-05-12

- Q: Concurrent action policy — what happens when two coroutines call Bot methods at the same time? → A: **Implicit composition with two intent slots.** Long-running movement methods (`walk_to`, `follow`, `dig`, `swim_to`, `fly_to`) take the **movement slot** and are mutually exclusive — a second call on the slot raises `BotBusy` (or waits if `wait_for_slot=True`). Instant-effect methods (`attack`, `interact_entity`, `look_at`, `look_by_vector`, `swing_arm`, `use_item`, `say`, `command`, `sneak`, `sprint`, `jump`, single `click_slot`) take the **action slot** which only serialises in-flight encode+send, so they freely interleave with movement (e.g., attack-on-the-move works). Container interaction (`open_chest`/`open_furnace` + subsequent clicks until `close_container`) holds a third **container slot**, mutually exclusive with itself but composable with movement and instant actions.
- Q: World cache eviction policy — what stays in memory? → A: **Server-driven only.** The World cache stores every chunk the server sends via `map_chunk` and evicts only when the server sends `unload_chunk`. No client-side LRU, no radius cap, no max-chunk count. This mirrors the server's authoritative view of what the bot can "see" — querying a block outside view distance is meaningless because the server itself has no fresh data for it. `bot.world.get_block(x, y, z)` returns `None` for any block in an unloaded chunk.
- Q: Auto-eat food selection — which food to eat when multiple types are available? → A: **Caller-supplied selector with a `BEST_SATURATION` default.** `auto_eat(threshold, picker=None)` accepts an optional callable `picker(eligible_items: list[ItemSlot]) -> ItemSlot` that picks which food to eat from the list of inventory food items. When `picker=None` (default), the framework uses `BEST_SATURATION`: highest `food_points + saturation_modifier` from the vanilla food table; ties broken by lowest slot index. The framework also exposes named pre-built pickers: `BEST_SATURATION`, `WORST_FIRST` (eat junk before the good stuff), `OLDEST_FIRST` (lowest slot index, predictable).
- Q: Entity metadata typed accessor scope — what subset of MC 1.20.1's ~50 entity types get typed Python accessors? → A: **Full coverage.** Every entity type defined in protocol 763 (all ~50 living, projectile, item, vehicle, decoration, and misc entities) gets typed Python accessors for every metadata index its server-side metadata table defines. Source-of-truth is PrismarineJS `minecraft-data` (`entities.json` + the metadata schemas in the entity-tracker source). Generic `entity.metadata[index]` access remains available as an escape hatch for custom/modded fields, but every vanilla index has a typed Pythonic accessor (e.g., `wolf.collar_color`, `villager.profession`, `horse.armor`, `creeper.is_charged`, `ender_dragon.phase`). Scope estimate: ~50 entity classes × 5-15 indices each ≈ 500-700 accessors, generated/scaffolded from the data table and verified by tests.
- Q: Physics tick strictness — what happens when a tick falls behind the 20 Hz schedule? → A: **Best-effort + server correction.** The auto-ticker schedules each tick 50 ms after the previous tick's start; if a tick takes longer than 50 ms, the next tick starts as soon as control returns to the event loop (no catch-up replays, no compensation sleep). Server-pushed `SynchronizePlayerPosition` packets correct any cumulative drift between local prediction and the server's authoritative state. For deterministic offline use (ML/RL, unit tests), the developer calls the public `bot.tick()` manually instead of relying on the auto-ticker.

## User Scenarios & Testing *(mandatory)*

The "users" of this feature are developers (and ML-agent code) that build
bots on top of the framework. After this milestone the developer can write
code like ``await bot.walk_to(100, 64, 100)`` and the bot **actually walks
there** — over slabs, through doors, across water, dodging holes — instead
of issuing raw packet sequences by hand.

This builds on the protocol foundation from milestone 001. Everything
under "raw packets / framing / Connection lifecycle" already exists; this
milestone adds the high-level **Bot** class and the supporting trackers
(World, Entities, Inventory) plus the physics tick and A* pathfinder
that make autonomous behaviour possible.

### User Story 1 - Walk to a Coordinate (Priority: P1) 🎯 MVP

A developer constructs a bot, asks it to ``walk_to(x, y, z)`` somewhere in
the loaded world, and the bot autonomously crosses the terrain — climbing
small ledges, descending safe drops, swimming across water, opening doors
in its path, jumping the gaps — until it arrives within reach of the
target or times out. The developer's code does not deal with per-tick
position packets, A* paths, collision math, or door-open packets; the bot
handles all of that.

**Why this priority**: Without autonomous movement there is no
"bot that does things". Every other behaviour (mining, attacking,
fetching, following) is built on top of a working ``walk_to``. This is
the MVP gate for the whole milestone.

**Independent Test**: A developer's 10-line script connects the bot,
calls ``await bot.walk_to(spawn.x + 50, spawn.y, spawn.z + 50, timeout=60)``,
and the bot arrives within 5 blocks of the target within 60 seconds
on a Paper 1.20.1 server.

**Acceptance Scenarios**:

1. **Given** the bot is in Play state on flat terrain with no obstacles,
   **When** the developer calls ``walk_to(target)`` within 100 blocks,
   **Then** the bot reaches a position within 1 block of the target
   within 30 seconds.
2. **Given** the bot needs to climb a 1-block ledge or stair-block,
   **When** ``walk_to(target)`` is called and the path requires going up,
   **Then** the bot transparently steps up the ledge without explicit
   jump calls from the developer.
3. **Given** the path crosses a closed door or fence gate, **When**
   ``walk_to`` is called, **Then** the bot opens the door on the way
   through and continues.
4. **Given** the path crosses water, **When** ``walk_to`` is called,
   **Then** the bot swims through (does not drown, does not get stuck
   on the water surface).
5. **Given** the path crosses a gap of one block, **When** ``walk_to``
   is called, **Then** the bot jumps the gap rather than falling in.
6. **Given** ``walk_to`` is called but the path is impossible (target
   inside a wall, no chunk loaded, isolated by lava), **When** A* fails
   or runs out of time, **Then** ``walk_to`` raises a typed error the
   developer can catch (e.g., ``NoPathFound``).

---

### User Story 2 - Observe the World and Entities (Priority: P1)

The bot maintains an accurate, queryable view of the world around it.
The developer can ask ``bot.world.get_block(x, y, z)`` and get the
current block name; ``bot.entities`` returns every tracked entity with
position, health, and metadata. The bot's view updates as the server
streams chunk and entity packets, without the developer writing any
packet-handling code.

**Why this priority**: Movement (US1) and inventory (US3) presuppose a
known world and a known set of entities. The two trackers (World cache,
Entity tracker) are the substrate every higher-level decision sits on.

**Independent Test**: A developer connects the bot, calls
``bot.world.find_blocks_nearby("oak_log", radius=32, limit=5)`` and
``bot.entities.nearby_players(radius=64)``. Both return non-empty results
in a populated test world within seconds of joining.

**Acceptance Scenarios**:

1. **Given** the bot has just entered PLAY state, **When** the initial
   chunk burst arrives, **Then** ``bot.world.get_block(spawn.x, spawn.y - 1,
   spawn.z)`` returns the block the bot is standing on within 1 second.
2. **Given** a block is broken nearby by another player, **When** the
   server sends the ``block_change`` packet, **Then** ``bot.world.
   get_block(x, y, z)`` returns the new block within one tick (50 ms).
3. **Given** a mob spawns within view distance, **When** the server
   sends ``spawn_entity``, **Then** the mob appears in ``bot.entities``
   with a typed display name (e.g., ``"Zombie"``), health, and position.
4. **Given** a sheep is in range, **When** the developer reads
   ``bot.entities.find_by_id(eid).metadata.wool_color``, **Then** they
   get the sheep's wool colour (or ``None`` if unknown).
5. **Given** a chunk goes out of view distance, **When** the server
   sends ``unload_chunk``, **Then** ``bot.world.get_block`` on a block
   in that chunk returns ``None`` (no stale data).

---

### User Story 3 - Inventory & Container Interaction (Priority: P1)

The developer reads what's in the bot's inventory, equips armor, moves
items between slots, opens chests and furnaces, and crafts at a crafting
table — all via Pythonic methods on ``bot.inventory``, ``bot.armor``,
and ``bot.open_chest(x, y, z)``. The bot reads item NBT (enchantments,
custom name, damage) and exposes typed fields the developer can inspect.

**Why this priority**: Many bot use-cases (survival farming, automation,
trade) require inventory mastery. Without it, the bot can move but
cannot affect the economy.

**Independent Test**: A developer in creative mode runs
``await bot.give("diamond_sword")``, ``await bot.equip_armor("diamond_helmet")``,
``await bot.open_chest(chest_pos)``, ``await bot.move_item(from_slot, to_slot)``.
Each step is visible in the in-game inventory UI and on the server side.

**Acceptance Scenarios**:

1. **Given** the bot is in PLAY state with items in its inventory,
   **When** the developer reads ``bot.inventory.items()``, **Then** they
   get a list of populated slots with item name, count, and NBT.
2. **Given** the bot is holding a damaged diamond pickaxe, **When**
   ``bot.held_item.damage`` is read, **Then** it returns the current
   damage value parsed from the item's NBT.
3. **Given** the bot is in front of a chest, **When**
   ``await bot.open_chest(x, y, z)`` is called, **Then** the bot opens
   the chest and ``bot.container.items()`` returns the chest's contents
   within 1 second.
4. **Given** the bot has a stack of oak_planks in slot 5, **When**
   ``await bot.move_item(from_slot=5, to_slot=9)`` is called, **Then**
   the stack moves and the server's inventory state matches within
   500 ms.
5. **Given** the bot is in front of a crafting table with the right
   ingredients in inventory, **When** ``await bot.craft("oak_planks",
   x=table_x, y=table_y, z=table_z)`` is called, **Then** the result
   appears in the bot's inventory.

---

### User Story 4 - Survive Autonomously (Priority: P2)

The bot can stay alive in survival mode without developer intervention
for routine threats. It eats from its inventory when food drops below a
threshold (``auto_eat``), digs blocks using the right tool with the
correct timing (``dig(x, y, z, tool=...)`` waits for the natural break
time), attacks hostile entities in reach (``attack(eid)``), and surfaces
status-effect changes (poison, regeneration) via events.

**Why this priority**: Without survival helpers, a bot dies within
minutes of spawning in survival mode and can't accomplish any
multi-hour task. Required for any farming/exploration agent.

**Independent Test**: A developer connects a bot in survival mode with
food in inventory and ``auto_eat=True``. Bot survives 10 minutes of idle
time (with hostile mobs around) without dying.

**Acceptance Scenarios**:

1. **Given** the bot's food level falls below 15 with food in inventory,
   **When** ``auto_eat`` is enabled, **Then** the bot equips and eats
   the food within 2 ticks and food rises back to full.
2. **Given** a target block of dirt at known coords, **When**
   ``await bot.dig(x, y, z)`` is called, **Then** the bot waits the
   correct natural break time (~750 ms for dirt by hand) and the block
   is gone server-side.
3. **Given** a zombie is within attack reach, **When**
   ``await bot.attack(zombie_eid)`` is called, **Then** the server
   registers damage on the zombie and (if it dies) the bot collects the
   drops.
4. **Given** the bot takes damage from a skeleton arrow, **When** the
   damage arrives, **Then** an ``EntityDamageEvent`` fires with the
   damage amount and source entity id.
5. **Given** the bot drinks a potion of regeneration, **When** the
   server applies the effect, **Then** ``bot.status_effects.has_effect(
   "regeneration")`` returns ``True`` and includes the amplifier and
   remaining duration.

---

### User Story 5 - Follow Another Entity (Priority: P2)

The bot tracks a moving target (another player, a tamed wolf) and
maintains a fixed distance from it, re-pathing as the target moves.
``await bot.follow(eid, distance=3, timeout=60)`` does the heavy
lifting; the developer just supplies the target and a distance.

**Why this priority**: Common pattern for utility bots (helper/escort).
Independent of attack so worth its own story.

**Independent Test**: A developer's bot follows another connected player
around the spawn area for 60 seconds; stays within 4 blocks the entire
time (per WireLog position).

**Acceptance Scenarios**:

1. **Given** another player is moving on flat terrain, **When**
   ``await bot.follow(player_eid, distance=3)`` is called, **Then** the
   bot stays within 4 blocks of the player for the entire follow
   duration.
2. **Given** the followed entity teleports far away, **When** the
   follow tick detects the gap, **Then** the bot re-paths via the world
   cache and resumes pursuit (or gives up after a configurable time if
   the target is unreachable).
3. **Given** the followed entity dies or is unloaded, **When** the
   tracker loses sight, **Then** ``follow`` resolves with a typed
   ``TargetLost`` error.

---

### User Story 6 - Behavior Trees for Composition (Priority: P3)

For complex agents, the developer composes the bot's primitives
(walk, eat, attack, dig) into trees with selectors, sequences, and
decorators. ``Selector([HasFoodLow & EatBest, IsThreatened & AttackNearest, Idle])``
expresses a survival policy in a few lines.

**Why this priority**: Optional but expected of any "framework"; ML/LLM
agent integrations will use these primitives. Lower priority than the
mechanics themselves.

**Independent Test**: A developer wires up a small behaviour tree —
"if hungry eat; else if mob nearby attack; else walk to spawn" — and
the bot's behaviour matches the policy on a populated server for 5
minutes.

**Acceptance Scenarios**:

1. **Given** a behaviour tree with three branches, **When** the bot's
   condition matches the first branch, **Then** the first action runs
   to completion before re-evaluating.
2. **Given** a decorator ``RepeatUntilFail(walk_to(target))``, **When**
   the bot reaches the target, **Then** the decorator re-issues
   ``walk_to`` until the condition fails.

---

### User Story 7 - Chat & Commands (Priority: P3)

The bot can read chat messages from other players and send chat or
slash-commands itself. ``bot.say("hello")`` is one line; an event hook
on ``ChatMessageEvent`` lets the developer react to commands like
"!come here".

**Why this priority**: Trivial to implement on top of US1 packets but
genuinely useful for human-in-the-loop bots. Lowest priority because
each acceptance scenario is just one packet.

**Independent Test**: Bot sends "hello"; the message appears in the
server console and other players see it. Another player types "!come";
the bot's hook fires with the parsed text.

**Acceptance Scenarios**:

1. **Given** the bot is in Play, **When** ``await bot.say("hi")`` is
   called, **Then** "hi" appears in the server chat within 500 ms.
2. **Given** another player types "/msg Bot hello", **When** the chat
   arrives, **Then** the bot's ``@bot.on(ChatMessageEvent)`` handler
   fires with the sender name and message text.
3. **Given** the bot is op, **When** ``await bot.command("/give @s diamond_pickaxe")``
   is called, **Then** the command runs and a diamond pickaxe appears
   in the bot's inventory.

---

### Edge Cases

- **Server teleports bot mid-walk** (e.g., death respawn, ``/tp``): the
  current walk-to aborts cleanly and surfaces a ``Teleported`` event
  rather than continuing to the now-stale target.
- **Target chunk unloads while walking**: walk-to detects missing world
  data, optionally waits for chunk re-load (with timeout), then aborts.
- **No path exists** (target walled off, isolated by lava): A* exhausts
  its node budget within a fixed time and raises ``NoPathFound``.
- **Bot falls into lava**: physics tick detects lava as floor type,
  developer-installed safety hook can react; default behaviour is to
  emit ``InLavaEvent`` and continue (no automatic escape — that's the
  developer's policy).
- **Server lag** during ``dig`` (block break time exceeds natural):
  ``dig`` waits up to 2× natural break time before raising
  ``DigFailed``.
- **Concurrent inventory clicks** (two coroutines call
  ``move_item`` on overlapping slots): the bot serialises clicks
  through a per-window lock; the second call observes the post-first
  state.
- **Container closed by another action mid-operation** (e.g., chunk
  unload closes a chest): pending operations on that container raise
  ``ContainerClosed``.
- **Bot inside a vehicle** (boat, minecart, horse): movement uses
  ``vehicle_move`` serverbound and the bot is aware its position is the
  vehicle's; ``walk_to`` either fails with ``InVehicle`` (caller
  dismounts first) or, future enhancement, drives the vehicle.
- **Disconnect mid-action**: any awaiting ``walk_to`` / ``dig`` /
  ``attack`` / ``open_chest`` raises ``ConnectionDropped`` per
  Connection's existing lifecycle.
- **Bot in another dimension** (Nether/End): world cache is per-
  connection-session; on dimension change (``respawn`` packet with new
  ``dimension``), the world cache resets.
- **Item NBT with unknown / custom tags**: NBT parsing tolerates
  unknown tags (preserves them as opaque ``NbtTag``); only specified
  paths (``Damage``, ``Enchantments``, ``display.Name``) get typed
  helpers.
- **Race between local prediction and server sync**: server-pushed
  ``SynchronizePlayerPosition`` always wins; local prediction is reset
  to server value.

## Requirements *(mandatory)*

### Functional Requirements

**Bot lifecycle and state**

- **FR-001**: The bot is constructed on top of an existing
  ``Connection`` from milestone 001 (or via a convenience factory that
  creates one). The bot owns the lifecycle of the per-session state
  (world cache, entities, inventory) and resets it across reconnects.
- **FR-002**: The bot exposes a read-only ``position`` ``(x, y, z)``
  property reflecting either its server-confirmed location or, between
  ticks, its locally-predicted location.
- **FR-003**: The bot exposes read-only ``health``, ``food``,
  ``saturation``, ``game_mode``, ``yaw``, ``pitch``, ``is_dead``,
  ``xp_level``, ``xp_total`` properties derived from incoming packets.
- **FR-004**: The bot's per-session state is cleared on dimension
  change (``respawn``), on disconnect, and on opt-in auto-reconnect.

**Physics**

- **FR-010**: A physics tick runs at a target rate of **20 Hz**
  (50 ms between ticks, matching the server tick rate) on the bot,
  computing gravity, collision, water drag, step-up of ≤ 0.6 blocks,
  and auto-sprint when the bot is moving toward a waypoint more than
  4 blocks away. The auto-ticker is **best-effort**: each tick is
  scheduled 50 ms after the previous tick's *start*. If a tick takes
  longer than 50 ms (slow host, GC pause, user hook), the next tick
  starts immediately on event-loop resume — no catch-up replays, no
  compensation sleep. Any cumulative drift between local prediction
  and the server's authoritative state is corrected by server-pushed
  ``SynchronizePlayerPosition`` packets (FR-011). For deterministic
  offline use (ML/RL, unit tests), the developer calls the public
  ``await bot.tick()`` manually instead of relying on the auto-ticker.
- **FR-011**: Local position prediction MUST be reset to the server's
  authoritative value when ``SynchronizePlayerPosition`` is received
  (consistent with the FR-006 teleport-confirm in 001).
- **FR-012**: The physics tick MUST handle blocks with non-cubic
  hitboxes correctly: slabs (top/bottom), stairs (top/bottom),
  carpets, candles, turtle eggs, lily pads, snow layers (1..7 high).
  The block-state ID determines hitbox shape.
- **FR-013**: Water physics: when the bot's feet are in water, gravity
  is reduced, horizontal speed is dragged, vertical impulse is available
  (swim-up), and the bot must not drown (auto-surfaces if breath low).

**Movement APIs**

- **FR-020**: ``await bot.walk_to(x, y, z, timeout=30.0, max_fall=3,
  wait_for_slot=False)`` navigates the bot to within 1 block of the
  target using A*. Holds the **movement slot** for its duration;
  raises ``BotBusy`` if the slot is already held and
  ``wait_for_slot=False`` (default), or queues otherwise. Raises
  ``NoPathFound`` if A* fails, ``WalkTimeout`` if elapsed >= timeout.
- **FR-021**: ``await bot.look_at(x, y, z)`` rotates yaw and pitch to
  point the bot's eye line at ``(x, y, z)``; arrives within 1 server
  tick.
- **FR-022**: ``await bot.look_by_vector(dx, dy, dz)`` rotates by a
  relative direction vector from current orientation.
- **FR-023**: ``bot.sneak(True/False)``, ``bot.sprint(True/False)``
  toggle sneaking and sprinting state (sent via ``entity_action`` per
  the protocol).
- **FR-024**: ``await bot.jump()`` initiates a single jump impulse
  on the next physics tick.
- **FR-025**: ``await bot.fly_to(x, y, z)`` (creative only) flies in a
  straight line to the target, bypassing the pathfinder.
- **FR-026**: ``await bot.follow(eid, distance, timeout,
  wait_for_slot=False)`` tracks another entity and maintains a target
  distance, re-pathing as the entity moves; resolves on ``timeout`` or
  ``TargetLost``. Holds the **movement slot** for its duration.
- **FR-027**: Bot defines three concurrency slots: **movement**
  (``walk_to`` / ``follow`` / ``fly_to`` / ``swim_to`` / ``dig``),
  **action** (``attack`` / ``interact_entity`` / ``look_at`` /
  ``look_by_vector`` / ``swing_arm`` / ``use_item`` / ``say`` /
  ``command`` / ``sneak`` / ``sprint`` / ``jump`` / single
  ``click_slot``), and **container** (``open_chest`` / ``open_furnace``
  / ``open_crafting_table`` and clicks while open). Each slot
  serialises calls within it; slots compose freely with each other
  (e.g., ``attack`` mid-``walk_to`` is allowed and expected). Calls
  contending for an already-held slot raise
  :class:`BotBusy` unless invoked with ``wait_for_slot=True``.

**Pathfinding**

- **FR-030**: An A* pathfinder produces a sequence of waypoints from
  the bot's current position to a target within the loaded world,
  using 8-directional moves with octile heuristic (√2 cost for
  diagonals, corner-cutting prevention).
- **FR-031**: The pathfinder is aware of vertical step-up (≤ 1 block
  jump) and step-down (configurable ``max_fall``, default 3 for
  survival / 4 for creative).
- **FR-032**: The pathfinder is aware of slabs and stair-blocks (bottom
  slab/stair acts as headroom-clear; top slab/stair counts as floor
  +0.5 block).
- **FR-033**: The pathfinder routes through water with a movement cost
  of 1.5 (vs 1.0 on land); allows entering water from above (fall-in)
  and exiting water (cost 2.0).
- **FR-034**: The pathfinder treats obstacles (closed doors, fence
  gates, trapdoors) as passable at +2.0 cost; the physics tick
  auto-opens these obstacles during traversal.
- **FR-035**: A* must terminate within a configurable node-budget
  (default 5000) and raise ``NoPathFound`` if the target is
  unreachable.

**World cache**

- **FR-040**: The world cache stores chunk-section data parsed from
  incoming ``map_chunk`` packets, including block-state IDs.
- **FR-041**: ``bot.world.get_block(x, y, z) -> int | None`` returns
  the block-state ID at world coordinates ``(x, y, z)``, or ``None``
  if the chunk is not loaded.
- **FR-042**: ``bot.world.get_block_name(x, y, z) -> str | None``
  returns the namespaced block name (e.g., ``"minecraft:oak_log"``)
  for the block at ``(x, y, z)``.
- **FR-043**: ``bot.world.is_solid(x, y, z)``,
  ``bot.world.is_navigable(x, y, z)``,
  ``bot.world.is_water(x, y, z)`` return the corresponding boolean
  predicates per the standard MC 1.20.1 block-state classification.
- **FR-044**: ``bot.world.find_blocks_nearby(name, radius, limit)``
  scans the loaded world within ``radius`` blocks of the bot's current
  position and returns up to ``limit`` matching positions, sorted
  ascending by distance.
- **FR-045**: The world cache updates on ``block_change``,
  ``multi_block_change``, ``unload_chunk``, and (when block-entity
  data changes) ``tile_entity_data``.
- **FR-046**: World cache eviction is **strictly server-driven**: a
  chunk is dropped from memory if and only if the server sends an
  ``unload_chunk`` packet for it. The framework MUST NOT impose its
  own LRU cap, radius cap, or maximum-chunk-count policy. ``get_block``
  on a coordinate in an unloaded chunk returns ``None``; the developer
  cannot ask "what was this block five minutes ago when the chunk was
  loaded" because the bot has no authoritative answer.

**Entity tracker**

- **FR-050**: The entity tracker maintains a mapping
  ``{entity_id: Entity}`` of every entity currently within view
  distance.
- **FR-051**: ``bot.entities.nearby_entities(radius, type_filter=None)``
  returns entities within ``radius`` blocks of the bot, optionally
  filtered by entity type, sorted ascending by distance.
- **FR-052**: ``bot.entities.nearby_players(radius)`` returns nearby
  player entities.
- **FR-053**: Each tracked Entity exposes the common shared fields
  ``id``, ``type``, ``position``, ``yaw``, ``pitch``, ``health``,
  ``display_name``, plus a raw ``metadata`` mapping
  ``{index: parsed_value}`` for the entity's current data-watcher
  stream. Per-entity-type subclasses (``Sheep``, ``Wolf``, ``Horse``,
  ``Villager``, ``Creeper``, ``ItemEntity``, ``Player``, etc. — one
  subclass per entity type in protocol 763) expose typed Python
  accessors for **every** metadata index that entity defines
  (e.g., ``sheep.wool_color``, ``sheep.is_sheared``,
  ``wolf.collar_color``, ``horse.armor_item``,
  ``villager.profession``, ``creeper.is_charged``,
  ``ender_dragon.phase``). The Entity returned by the tracker for a
  given ``entity_id`` is the appropriate subclass instance based on
  the ``type`` field of the spawn packet.
- **FR-056**: Entity metadata schemas (which index maps to which
  field, for which entity type) ship as a generated data table at
  ``protocol-data/v763/entity_metadata.json``, derived from
  PrismarineJS ``minecraft-data`` (``entities.json`` +
  ``protocol.json`` ``entityMetadata`` switch table). The table is
  consumed by code-gen tooling that produces the per-entity-type
  subclass files (one file per entity type in
  ``protocol/v763/entities/``), each with the typed accessors
  declared as properties over ``metadata[index]``. Unknown / modded
  metadata indices fall through to the raw ``entity.metadata`` map
  without raising.
- **FR-054**: ``await bot.attack(eid)`` sends ``use_entity`` with
  attack semantics; ``await bot.interact_entity(eid)`` sends
  ``use_entity`` with interact semantics; both swing the bot's main
  hand.
- **FR-055**: Entity state updates on ``spawn_entity``,
  ``spawn_entity_experience_orb``, ``named_entity_spawn``,
  ``entity_velocity``, ``rel_entity_move``, ``entity_look``,
  ``entity_move_look``, ``entity_teleport``, ``entity_metadata``,
  ``entity_destroy``, ``entity_status``.

**Inventory**

- **FR-060**: ``bot.inventory.items()`` returns a list of all
  non-empty player inventory slots with item id, count, NBT, and
  resolved item name.
- **FR-061**: ``bot.inventory.hotbar_items()`` returns the 9 hotbar
  slots.
- **FR-062**: ``bot.container.items()`` returns slots of the currently
  open container window (chest/furnace/crafting table); empty if no
  container is open.
- **FR-063**: ``await bot.select_slot(0..8)`` changes the held hotbar
  slot via ``held_item_slot`` serverbound; the change is reflected in
  ``bot.held_item`` immediately on server ack.
- **FR-064**: ``await bot.move_item(from_slot, to_slot)`` performs
  the appropriate ``window_click`` sequence to move the stack from
  ``from_slot`` to ``to_slot``; updates local state from incoming
  ``set_slot`` packets.
- **FR-065**: ``await bot.click_slot(slot, button, mode)`` is the raw
  ``window_click`` escape hatch for power-users.
- **FR-066**: ``await bot.drop_item(slot=None, full_stack=False)``
  drops the item in ``slot`` (or current held item if ``None``);
  ``full_stack=True`` drops the whole stack.
- **FR-067**: ``bot.inventory.find_item(name)`` returns the first slot
  containing an item with the given name (or ``None``);
  ``bot.inventory.count_item(name)`` returns the total count across
  all slots.
- **FR-068**: Each item slot exposes parsed NBT fields:
  ``damage`` (Damage tag), ``enchantments`` (list of
  ``(id, level)`` tuples from Enchantments tag), ``display_name``
  (display.Name JSON), ``custom_model_data`` (CustomModelData int).
  Other NBT remains accessible as the raw ``NbtTag`` via
  ``slot.nbt``.
- **FR-069**: ``await bot.equip_armor(item_name)`` finds the item in
  inventory and moves it to the correct armor slot;
  ``await bot.unequip_armor(slot_name)`` moves armor from the slot
  back to the first available player slot.
- **FR-070**: ``await bot.swap_to_offhand(slot)`` moves the item from
  ``slot`` to the offhand slot (or vice-versa).

**Containers**

- **FR-080**: ``await bot.open_chest(x, y, z)`` interacts with the
  chest block, waits for ``open_screen`` server packet, returns once
  the container is open; ``bot.container`` is then populated.
- **FR-081**: ``await bot.open_furnace(x, y, z)`` is the equivalent
  for furnaces (with separate input / fuel / output slot helpers).
- **FR-082**: ``await bot.open_crafting_table(x, y, z)`` is the
  equivalent for a crafting table.
- **FR-083**: ``await bot.close_container()`` sends ``close_window``
  serverbound and clears ``bot.container``.
- **FR-084**: ``await bot.craft(recipe_or_grid, x, y, z)`` opens the
  crafting table at ``(x, y, z)``, lays out the recipe, and collects
  the result into player inventory.
- **FR-085**: ``await bot.smelt(input_item, fuel_item, x, y, z)``
  opens the furnace at ``(x, y, z)``, places fuel and input, and
  collects the output when ready.

**Survival helpers**

- **FR-090**: ``bot.auto_eat(threshold=15, eat_duration=1.6,
  picker=None)`` registers a hook: when ``bot.food < threshold`` and
  the inventory contains any food item, the bot equips it,
  right-clicks for ``eat_duration`` seconds, and food returns to full.
  ``picker`` is an optional ``Callable[[list[ItemSlot]], ItemSlot]``
  that selects which food to eat from the eligible list; defaults to
  the framework-provided ``BEST_SATURATION`` strategy
  (max ``food_points + saturation_modifier`` from the vanilla food
  table, ties broken by lowest slot index). The framework also
  exports the pre-built pickers ``BEST_SATURATION``, ``WORST_FIRST``
  (eat lowest-nutrition items first), and ``OLDEST_FIRST`` (lowest
  slot index, deterministic).
- **FR-091**: ``bot.in_reach(x, y, z, max_dist=4.5)`` returns
  ``True`` if the bot's eye position is within ``max_dist`` blocks of
  the target (matching vanilla reach semantics).
- **FR-092**: ``await bot.dig(x, y, z, tool=None)`` starts digging
  the block at ``(x, y, z)``, waits the appropriate natural break
  time for the block + the currently-held tool, then finalises the
  dig via ``block_dig`` status=2.
- **FR-093**: ``bot.status_effects`` exposes the active potion
  effects as ``{name: (amplifier, duration_ticks)}``;
  ``has_effect(name)`` returns ``True`` if the effect is currently
  active.

**Events & hooks (PyTorch-style)**

- **FR-100**: ``@bot.on(EventType)`` decorator registers a handler;
  ``bot.subscribe(event_type, handler)`` is the imperative form;
  ``bot.unsubscribe(handler)`` removes one.
- **FR-101**: The bot defines typed events for every observable
  state-change: ``ChatMessageEvent`` (incoming chat),
  ``EntityDamageEvent``, ``EntityDeathEvent``,
  ``ItemPickupEvent``, ``InventoryChangeEvent``,
  ``BlockBreakEvent`` (when *another* entity breaks a block),
  ``ContainerOpenEvent``, ``ContainerCloseEvent``,
  ``Reconnected``, ``Teleported``, ``InLavaEvent``,
  ``DimensionChangedEvent``.
- **FR-102**: ``bot.drain_events()`` returns and clears all events
  received since the last drain; ``await bot.next_event(event_type,
  timeout)`` resolves to the next event of the given type.

**Chat & commands**

- **FR-110**: ``await bot.say(message)`` sends a chat message via
  ``chat_message`` (offline-mode unsigned).
- **FR-111**: ``await bot.command(slash_command)`` sends a slash
  command via ``chat_command`` (offline-mode unsigned).
- **FR-112**: Incoming ``player_chat``, ``profileless_chat``, and
  ``system_chat`` packets fire ``ChatMessageEvent`` with a
  best-effort parsed sender name and message text.

**Behaviour trees (optional submodule)**

- **FR-120**: A separate ``minecraft_bot.behaviour`` submodule provides
  composable async nodes: ``Selector``, ``Sequence``, ``Inverter``,
  ``RepeatUntilFail``, ``AlwaysSucceed``, ``Condition``, ``Action``.
- **FR-121**: A node executes via ``await node.run(bot, ctx)``;
  returns one of ``Success | Failure | Running``.
- **FR-122**: Built-in primitives wire to bot methods:
  ``WalkTo(x, y, z)``, ``AttackNearest(filter)``,
  ``EatWhenHungry(threshold)``, ``FollowPlayer(name)``,
  ``DropItem(slot)``, ``Say(message)``.

**Architecture invariants**

- **FR-130**: The Bot class is built strictly on top of the public
  ``Connection`` from 001 — it does not bypass the framer, registry,
  or write lock.
- **FR-131**: All state (world, entities, inventory) is per-Bot; no
  shared mutable globals (continues 001's multi-bot-ready architecture
  per FR-017a of 001).
- **FR-132**: The Bot uses only the Python stdlib + the
  ``minecraft_bot`` core package (Constitution VI).
- **FR-133**: The physics tick is a separate async task spawned at
  ``bot.start()`` and cancelled at ``bot.disconnect()``; it does NOT
  share state mutably with the decode loop's task except via thread-
  safe asyncio primitives.
- **FR-134**: The Bot's public API is representable on the PyO3
  boundary (`Send + 'static`, no raw pointers) so a future Rust
  port can replace internals without changing the developer-facing
  Python API.

**Quality**

- **FR-140**: Each public Bot method has at least one unit test that
  exercises it against a deterministic fake server / replayed
  WireLog OR a live-server integration test.
- **FR-141**: A live-server smoke test exercises all P1 stories
  (US1, US2, US3) end-to-end against Paper 1.20.1 and MUST pass
  before any change to physics, pathfinding, world cache, entity
  tracker, or inventory tracker is merged.

### Key Entities

- **Bot** — the user-facing handle. Owns a Connection, a World cache,
  an EntityTracker, an InventoryTracker, a physics-tick task, and a
  registry of event hooks.
- **BotSnapshot** — frozen point-in-time view of bot's position /
  health / inventory; useful for ML observation pipelines.
- **World** — voxel cache of chunk data. Exposes ``get_block``,
  ``get_block_name``, ``is_solid``, ``find_blocks_nearby``.
- **Chunk** — a single 16×N×16 chunk's block-state storage.
- **Entity** — tracked entity record (id, type, position, health,
  metadata, display_name).
- **EntityTracker** — collection of Entities; updates on entity-related
  packets.
- **InventoryTracker** — bot's player inventory plus open-container
  state; updates on ``set_slot`` / ``window_items``.
- **ItemSlot** — a single populated inventory slot with parsed NBT
  helpers (damage, enchantments, display_name).
- **Path** — A* result: a sequence of ``(x, y, z)`` waypoints with
  associated edge cost.
- **PhysicsState** — per-tick simulation state: velocity, on_ground,
  in_water, motion_blocked_by, last_step_up.
- **BehaviorNode** — base class for tree composition; concrete
  subtypes are ``Selector``, ``Sequence``, ``Inverter``, etc.
- **Event** — base class for hookable events; concrete subtypes per
  FR-101.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A bot can ``walk_to`` a target **100 blocks away on
  flat terrain with no obstacles** within **30 seconds** in survival
  mode.
- **SC-002**: A bot can ``walk_to`` a target **50 blocks away through
  a mixed terrain of stairs, slabs, water, and a closed door** within
  **60 seconds**.
- **SC-003**: When another player breaks a nearby block, ``bot.world.
  get_block(x, y, z)`` reflects the change within **one server tick
  (50 ms)**.
- **SC-004**: Entity tracker reflects an entity's new position within
  **one server tick** of receiving the protocol packet.
- **SC-005**: ``open_chest`` opens the container and ``container.items()``
  matches the in-game chest contents 100 % of the time across **50
  repeated trials**.
- **SC-006**: A bot with ``auto_eat`` enabled and ≥ 5 cooked food
  items in inventory survives **10 minutes idle in spawn area** with
  hostile mobs present (no death from hunger or single mob hit).
- **SC-007**: A bot can attack a zombie within 4 blocks and kill it
  in **under 30 seconds** (assumes 10 hits with bare hands; a sword
  cuts the time).
- **SC-008**: A bot can find 5 nearest ``oak_log`` blocks within
  radius 32 in **under 100 ms**, given the chunks are loaded.
- **SC-009**: ``Bot.tick()`` executes one physics tick in
  **under 5 ms median, ≤ 25 ms p99** on commodity hardware.
- **SC-010**: A behaviour tree of depth 4 with 10 nodes evaluates
  one iteration in **under 1 ms median**.
- **SC-011**: A live-server smoke test exercising US1+US2+US3
  completes in **under 5 minutes** wall-clock and is part of the
  default Bot-API test command.
- **SC-012**: A developer can write a fully working "follow this
  player" bot in **under 30 lines** of Python code.

## Assumptions

- The protocol foundation milestone (001) is complete and provides
  ``Connection``, all 176 protocol-763 packets, the framer, and the
  WireLog. This milestone strictly builds on top.
- Initial scope is **protocol 763 / Minecraft 1.20.1** only (matches
  001).
- Test target is the configured **Paper 1.20.1 server at
  172.26.160.1:25565**, online_mode=false.
- **Single-bot scope**: the API is designed for one ``Bot`` per
  ``Connection``. ``BotPool`` and multi-bot orchestration are
  **out of scope** for this milestone but the architecture stays
  multi-bot-ready (continues FR-017a from 001).
- **Online-mode authentication** is out of scope (continues 001's
  scope decision).
- **ML/RL adapters** (Gymnasium env, neural observation/action
  shapes) are out of scope; the Bot exposes the substrate (
  ``BotSnapshot``, events) on which an adapter can be built later.
- **PyO3 bridge** is a separate later milestone; Bot's public API
  must remain PyO3-representable (FR-134).
- The existing ``~/Python/python-mc/`` repository (v0.11.0, 102/102
  test suites green) is used as an **algorithmic reference** —
  inspect for proven approaches to A*, physics, NBT parsing,
  inventory clicks — but no code is copy-pasted; this milestone owns
  its own implementation under the Constitution-mandated structure
  (one-file-per-packet, frozen dataclass, zero deps).
- **World cache is in-memory only**; no disk persistence in this
  milestone.
- **Chunk decode** is the largest remaining unstructured payload in
  001's clientbound packets (``map_chunk`` is captured as opaque
  bytes). This milestone adds structured chunk decoding as part of
  the World cache implementation.
- **Block-state ID table** for protocol 763 (~21000 block states
  across ~750 block types) ships as a generated data table under
  ``protocol-data/v763/block_states.json`` derived from PrismarineJS
  ``minecraft-data``.
- Entity metadata schemas for the ~50 entity types in 1.20.1 ship as
  a generated data table; this milestone implements the metadata
  stream decoder that ``entity_metadata`` packet currently captures
  as opaque bytes, plus **typed Python accessors for every index of
  every entity type** (per Q4 clarification — full coverage, ~50
  subclasses × 5-15 indices each ≈ 500-700 accessors, scaffolded
  from `protocol-data/v763/entity_metadata.json`).
