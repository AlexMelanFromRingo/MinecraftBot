# Phase 0 Research: Bot API

**Date**: 2026-05-12
**Plan**: [plan.md](./plan.md)

This document records the load-bearing technology and design decisions
that back the Bot API plan. There are no unresolved `NEEDS
CLARIFICATION` markers entering Phase 1 — the spec's `## Clarifications`
session resolved the five highest-impact questions (concurrent action
slots, world cache eviction, auto-eat picker, full entity metadata
coverage, best-effort physics tick) before planning began.

For each topic: **Decision · Rationale · Alternatives considered ·
Sources**.

---

## R-01 Chunk-data structured decoder

**Decision**: Implement a structured decoder for the `map_chunk`
packet that 001 currently captures as opaque bytes. The decoder
produces a `Chunk` object holding 16 to 24 `ChunkSection`s, each
containing a `PalettedContainer` of block states and a paletted
container of biomes. Heightmaps are decoded into typed long-packed
arrays; block-entity NBT records are stored as a list of
`BlockEntityRecord` (position + type + nbt).

The decoder lives at `python/minecraft_bot/world/decode_chunk.py`
(~600 lines). It calls into 001's NBT codec for the heightmap NBT and
into a new `PalettedContainer` parser for the section data.

**Rationale**:
- World cache (US2) is impossible without structured chunk data —
  every `get_block(x, y, z)` query needs the per-section paletted
  container.
- Constitution VII (Observability and Determinism): WireLog still
  captures raw bytes, so decode + re-encode round-trip is verifiable.
- Constitution VI: pure-stdlib (struct + bit math + 001's NBT).

**Alternatives considered**:
- **Stay opaque, parse lazily on first `get_block`**. Rejected:
  amortised decode is fine, but a cold `find_blocks_nearby` call
  would still need to walk the whole chunk; might as well decode on
  arrival.
- **Re-export PrismarineJS `prismarine-chunk` somehow**. Rejected:
  Node.js dependency, violates Constitution VI, and would force a
  transcoding layer.

**Sources**: minecraft.wiki "Chunk Format" section; PrismarineJS
`prismarine-chunk` source (algorithmic reference only); old
`python-mc/world.py` (working in-tree reference, but not copy-pasted).

---

## R-02 A* pathfinder

**Decision**: 8-directional A* with octile heuristic. Open set is a
`heapq` (binary min-heap keyed by f-score). Closed set is a `dict`
mapping `(x, y, z)` to best g-score so far. Neighbor generation
considers ±X, ±Z, ±diagonal-XZ, plus ±1 Y on each (jump or fall) when
the corresponding floor/ceiling conditions allow. Corner-cutting is
prevented (a diagonal move requires both adjacent cardinal moves to
be legal).

Costs: 1.0 for cardinal flat, √2 (~1.414) for diagonal, 1.5 for water
entry/swim, 2.0 for water exit, +2.0 surcharge for navigable obstacles
(closed doors / fence gates / trapdoors — the physics tick opens
these during traversal).

Vertical: step up ≤ 1 block when the block above the destination is
non-solid and the destination floor is solid (or a top-half slab/stair
acts as +0.5 height — handled identically to a regular climb).
Fall: configurable `max_fall` (default 3 for survival, 4 for creative).

Termination: A* halts when the open set is empty (no path) or after
the configurable `max_nodes` budget is exceeded (default 5000) —
raise `NoPathFound`.

**Rationale**:
- 8-dir matches every existing Minecraft bot framework (Mineflayer,
  python-mc, prismarine-pathfinder) and gives "diagonal natural" paths.
- Octile heuristic is admissible (never overestimates) so A* yields
  optimal paths up to the diagonal cost.
- Water cost 1.5 mirrors python-mc's value, which converged after
  live testing on the same Paper version.
- Configurable max-nodes prevents pathological searches from blocking
  the event loop.

**Alternatives considered**:
- **JPS (Jump Point Search)**. Rejected: extra complexity for marginal
  wins on small (radius ≤ 100) Minecraft paths.
- **D* Lite for incremental replanning**. Rejected: scope creep; the
  spec's `follow` is fine with periodic A* reruns.

**Sources**: classic A*; python-mc/navigation.py (working reference);
Mineflayer's prismarine-pathfinder design notes; spec FR-030 / 035.

---

## R-03 Physics tick

**Decision**: 20 Hz best-effort tick per FR-010 / Q5. Each tick
computes:

1. **Inputs**: current movement intent (walk_to waypoint, follow target,
   sneak/sprint/jump flags from API).
2. **Velocity update**: apply gravity (–0.08 vertical per tick, 0.02 in
   water), apply directional acceleration toward the active waypoint,
   apply friction (0.91 ground, 0.546 air, 0.8 water).
3. **Collision resolution**: AABB sweep against world voxels with step-up
   logic (≤ 0.6 blocks climbed without an explicit jump impulse).
4. **Position update**: apply velocity, clamp to collision result.
5. **Obstacle auto-open**: if the resolved position crosses a navigable
   obstacle (door/gate/trapdoor), emit the appropriate `block_place` /
   `interact` packet to open it before the bot would step into it.
6. **Server sync**: send `position_look` (or `position` / `look` /
   `flying` per which fields changed) every tick. Server's
   `SynchronizePlayerPosition` always wins on conflict.

Constants chosen to match vanilla MC physics within tolerance of
±0.01 block per tick (sufficient for ML/RL determinism in our test
suite).

**Rationale**:
- 20 Hz matches server tick rate → server reconciliation is one-tick
  granularity, minimal "moved too quickly" risk.
- Best-effort scheduling lets the event loop also handle decode
  burst without losing the tick contract (server corrects drift).
- AABB sweep with step-up is the standard MC physics approach;
  reference impl in python-mc/physics.py.

**Alternatives considered**:
- **Server-only movement (no local prediction)**. Rejected: every
  movement would wait round-trip latency; bot would feel laggy.
- **Higher tick rate** (e.g., 60 Hz interpolation). Rejected: server
  authoritative at 20 Hz; extra ticks would just send redundant
  packets.

**Sources**: minecraft.wiki "Entities" / "Player Movement" pages;
python-mc/physics.py; spec FR-010 / FR-012 / FR-013.

---

## R-04 Entity metadata stream + per-type subclasses (FULL coverage)

**Decision**: Implement a structured entity-metadata stream codec at
`python/minecraft_bot/entities/metadata.py` that decodes the
`entity_metadata` packet's payload (currently opaque in 001) into a
`{index: value}` map. Each value's type is determined by the
metadata-type byte in the stream (per the MC 1.20.1 entity-metadata
type table — Byte / VarInt / VarLong / Float / String / Chat /
OptChat / Slot / Bool / Rotations / Position / OptPosition /
Direction / OptUUID / BlockState / OptBlockState / NBT / Particle /
VillagerData / OptVarInt / Pose / CatVariant / FrogVariant /
OptGlobalPos / PaintingVariant / SnifferState / Vec3f / Quaternion).

On top of that, generate ~50 per-type Entity subclass files under
`entities/types/`. Each subclass:

- declares typed Python `@property` accessors for every metadata index
  the entity defines (per `protocol-data/v763/entity_metadata.json`);
- inherits common bases (`Entity → Living → Mob → Player` etc.) so
  shared accessors aren't duplicated;
- registers itself in `entities/types/__init__.py`'s type-id → class
  map so the tracker constructs the right subclass on `spawn_entity`.

The subclass files are **scaffolded** by `tools/generate_entity_
subclasses.py` from the data table and then **hand-tuned** for
docstrings, special accessors (e.g., wolf's tame-owner UUID resolved
to name), and edge cases. After scaffolding the files are owned by
humans (Constitution II spirit — one file per typed concept).

The metadata schema source-of-truth is PrismarineJS
`minecraft-data`'s `entities.json` + the metadata switch table embedded
in their `protocol.json`. Where the data is incomplete or wrong, a
companion `protocol-data/v763/entity_metadata_overrides.json` can
correct it.

**Rationale**:
- Q4 clarification chose full coverage (~500-700 typed accessors).
  Scaffolding via codegen is the only realistic way to ship that
  volume with correctness.
- Per-type subclasses give static-typing benefits (IDE autocomplete,
  type checkers spot wrong access patterns) without bloating runtime.
- Inheritance hierarchy (Living → Mob → Player → SpecificEntity)
  keeps shared accessors DRY.

**Alternatives considered**:
- **Single Entity class with `entity.get_metadata(index)`**. Rejected:
  loses static typing; users have to look up index numbers from MC
  wiki to use the data.
- **Codegen from upstream + never hand-edit**. Rejected: upstream
  data is incomplete (e.g., some metadata indices are unnamed or
  wrongly typed); we need the override path.

**Sources**: minecraft.wiki "Entity Metadata" page; PrismarineJS
`minecraft-data` `entities.json`; old `python-mc/entities.py`
(entity-specific helpers as reference).

---

## R-05 Inventory click protocol

**Decision**: Implement the `window_click` serverbound packet
sequences as a thin protocol layer in
`python/minecraft_bot/inventory/window.py`. The five high-level
operations the Bot API exposes map to specific (mode, button,
slot, state_id, changed_slots, carried_item) tuples:

- `pickup(slot)` — mode 0 button 0
- `pickup_half(slot)` — mode 0 button 1
- `quick_move(slot)` (shift-click) — mode 1 button 0
- `swap_with_hotbar(slot, hotbar_idx)` — mode 2 button hotbar_idx
- `drop_one(slot)` / `drop_stack(slot)` — mode 4 button 0/1
- `clone(slot)` (creative middle-click) — mode 3 button 2

For composite operations (`move_item(from, to)` = pickup + pickup):
the window helper computes the optimistic local-state delta and
includes it in the click's `changed_slots` array so the server can
detect (and reject) state divergence.

`state_id` comes from the most recently received `set_slot` /
`window_items` packet; the helper increments it after each successful
click.

**Rationale**:
- The window_click protocol is heavily under-documented and
  bug-prone; centralising the mapping in one helper module
  eliminates per-call repetition.
- Optimistic local state + state_id matches Notchian client behaviour
  exactly, avoiding mid-action sync issues.

**Alternatives considered**:
- **Caller constructs `window_click` packets directly**. Rejected:
  defeats the high-level API purpose; users would still need to know
  the mode/button matrix.

**Sources**: minecraft.wiki "Click Container" (serverbound 0x0B);
python-mc/inventory.py.

---

## R-06 Container interaction (open + RMB+scan craft)

**Decision**: `open_chest(x, y, z)` sends `use_item_on_block`
(serverbound 0x31, naming `block_place` in our codebase) targeting
the chest face. The bot then `await`s a clientbound `open_screen`
packet (0x30) and a follow-up `window_items` (0x12) before
`bot.container` is populated.

Crafting via crafting table uses the **RMB+scan** pattern that
python-mc proved on Paper 1.20.1: open the crafting table window,
place ingredients into specific slots via `window_click`, read the
result from the `window_items` for slot 0 (the output slot), then
shift-click slot 0 to collect.

Furnace smelting is similar: place fuel in slot 1, input in slot 0,
poll `window_items` for output in slot 2.

**Rationale**:
- RMB+scan is the only universal cross-server-mod approach to
  crafting (works on vanilla, Paper, Spigot, Folia).
- The synchronous open → settle → click pattern keeps the bot's
  `bot.container` state consistent.

**Alternatives considered**:
- **Single `craft_recipe_request` (serverbound 0x1B) which lets the
  server auto-fill the grid**. Rejected: server-side behaviour for
  this packet varies between vanilla and modded servers; RMB+scan is
  the conservative default.

**Sources**: python-mc/inventory.py; spec FR-080…FR-085.

---

## R-07 Food table + auto-eat pickers

**Decision**: Ship a generated `protocol-data/v763/foods.json` with
`item_id → {food_points: int, saturation_modifier: float, can_always_eat: bool}`
for every food item in 1.20.1 (apple, bread, steak, golden_carrot, …).
Source: PrismarineJS `minecraft-data`'s `foods.json`.

The `inventory/food.py` module exposes three named pickers per FR-090:

- `BEST_SATURATION`: max `food_points + saturation_modifier * 2`
  (ties broken by lowest slot index).
- `WORST_FIRST`: same metric, minimised.
- `OLDEST_FIRST`: lowest slot index, deterministic.

All three are simple callables matching the
`Callable[[list[ItemSlot]], ItemSlot]` signature. Users may pass a
custom callable.

Auto-eat firing: a periodic check (every 5 ticks = 250 ms) reads
`bot.food`; if below threshold and the inventory has any food item,
the picker selects one, `await bot.select_slot(slot)`, then
`await bot.use_item(hand=0)` (right-click main hand), wait 1.6 s
(eat duration), and food resets to full (server-confirmed via
`update_health` packet).

**Rationale**:
- Generated foods table is the only correct way to handle the long
  vanilla food list.
- Picker callable is composable and testable in isolation.
- 5-tick polling rate avoids busy-spinning.

**Sources**: minecraft.wiki "Food"; minecraft-data foods.json; spec
FR-090.

---

## R-08 Behaviour tree node interface

**Decision**: Async-flavoured nodes. Each node implements:

```python
async def tick(self, bot: Bot, ctx: BTContext) -> NodeStatus
```

where `NodeStatus ∈ {Success, Failure, Running}`. Composite nodes
(`Selector`, `Sequence`) iterate over children and aggregate per the
classic BT semantics (Sequence: first Failure short-circuits;
Selector: first Success short-circuits; Running propagates up
immediately).

Decorators (`Inverter`, `RepeatUntilFail`, `AlwaysSucceed`) wrap a
single child.

Conditions (`Condition`) wrap a predicate returning bool.

Actions (`Action`) wrap a bot coroutine; the action holds a slot
(via FR-027) for its duration.

Re-entrancy: a node's `tick()` is called repeatedly while it returns
`Running`. State is held in `ctx` (a per-tree dict) so multiple
ticks see consistent state.

**Rationale**:
- Async tick matches Python's natural async flow and integrates with
  the Bot's slot model.
- Status enum is the classical BT shape — minimal surface area, easy
  to understand.

**Alternatives considered**:
- **Sync nodes with blocking calls**. Rejected: would block the
  event loop.
- **Generator-based coroutines**. Rejected: async/await is the
  modern Python idiom.

**Sources**: classic Behaviour Tree literature; python-mc/behaviour.rs
(Rust impl as reference for the node interface).

---

## R-09 Test strategy for physics + pathfinding

**Decision**: Both physics and pathfinding are pure functions over
data inputs (PhysicsState + World, or A* over a synthetic World).
Test offline with deterministic synthetic data:

- **Physics tests** build a tiny synthetic World (a 16×16 floor + a
  step + a water column), construct a `PhysicsState`, run `bot.tick()`
  N times, and assert position evolution matches the closed-form
  expected trajectory.

- **A* tests** build synthetic World maps as ASCII art (`#` = solid,
  `.` = air, `~` = water, `D` = door, `S` = start, `T` = target),
  parse them into a World, run A*, and assert the returned path
  matches the expected shortest-path coordinates.

Live tests cover end-to-end behaviour (US1 walk_to flat + mixed
terrain) but the unit-test layer carries the bulk of correctness
proof for the pathfinder and physics components.

**Rationale**:
- Offline determinism is mandatory per FR-140 (each Bot method has a
  test that's either offline-deterministic or live).
- Synthetic Worlds let us cover edge cases (one-block gap, narrow
  staircase, door across path) without needing those terrains on
  the live server.

**Sources**: spec FR-140 / FR-141.

---

## R-10 Codegen-then-tune workflow for entity subclasses

**Decision**: `tools/generate_entity_subclasses.py` reads
`protocol-data/v763/entity_metadata.json` and produces a stub file
per entity type at `entities/types/{snake_case_name}.py` containing:

```python
class Sheep(Animal):
    """Sheep entity (id 92)."""

    ENTITY_TYPE_ID = 92

    @property
    def wool_color(self) -> int:
        return self.metadata.get(17, 0) & 0x0F

    @property
    def is_sheared(self) -> bool:
        return (self.metadata.get(17, 0) & 0x10) != 0
```

The codegen is **idempotent** — re-running it with `--force` only
re-scaffolds the typed accessors marked with a `# auto-generated`
comment block, preserving hand-tuned content elsewhere in the file.

Tests verify shape: `tests/python/unit/test_entity_subclass_shape.py`
asserts each entity-type-id from the data table has a corresponding
subclass with the expected accessors (analogous to 001's
`test_packet_shape.py`).

**Rationale**:
- One-shot codegen + idempotent re-run gives the best of both worlds:
  bulk generation for the boring boilerplate, hand-tuning where the
  data table is incomplete or where a special-case helper adds
  value.
- The shape test prevents accidental drift between the data table and
  the code.

**Sources**: 001 codegen pattern (`tools/generate_packet_skeletons.py`);
spec FR-053 / FR-056.

---

## Open items deferred to implementation

These will be settled when their tasks are touched, not pre-decided here:

- Exact constants for vanilla physics (gravity, friction, drag) —
  picked from minecraft.wiki tables at implementation time and
  verified by physics tests.
- Block-state ID classification for "solid / navigable / water" —
  built from `protocol-data/v763/block_states.json` properties; rule
  set inherited from python-mc and adjusted as live tests reveal
  discrepancies.
- Entity AABB hitboxes — sourced from minecraft.wiki "Entity" pages
  per type; landed as `protocol-data/v763/entity_hitboxes.json`.

---

## Summary

All Phase 0 research items resolved. No `NEEDS CLARIFICATION` remains.
Plan is consistent with Constitution v1.0.0. Ready to proceed to Phase
1 design artefacts.
