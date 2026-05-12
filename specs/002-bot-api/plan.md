# Implementation Plan: Bot API

**Branch**: `002-bot-api` | **Date**: 2026-05-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-bot-api/spec.md`

## Summary

Build a high-level **Bot** API on top of the protocol foundation
delivered in milestone 001. The Bot exposes Pythonic methods for the
things a developer actually wants — `walk_to(x, y, z)`, `attack(eid)`,
`open_chest(pos)`, `dig(pos)`, `follow(eid)`, `auto_eat()` — and is
backed by four trackers (World, EntityTracker, InventoryTracker,
StatusEffects), a 20-Hz physics tick, and an 8-directional A*
pathfinder. The 3-slot concurrency model (movement / action /
container) lets a bot attack on the move and look around while
walking. Full typed metadata accessors for ~50 entity types replace
001's opaque `entity_metadata` payload. World cache is server-driven
(no LRU, no radius cap — only `unload_chunk` evicts).

The optional `behaviour` submodule provides composable async nodes
(Selector, Sequence, Inverter, RepeatUntilFail, …) for tree-shaped
agent logic without forcing it on simple bots.

PyO3 and BotPool are explicitly deferred to later milestones; the API
shape is designed to cross those boundaries unchanged.

## Technical Context

**Language/Version**: Python 3.11+ (canonical reference, continues 001).
Rust mirror is deferred to a later milestone (003); the Python public
surface designed here must remain PyO3-representable
(`Send + 'static`, no raw pointers — FR-134).

**Primary Dependencies**:
- Python core: **stdlib only** per Constitution VI — `asyncio`,
  `dataclasses`, `enum`, `struct`, `math`, `heapq` (for A* open-set),
  `collections` (deque), `time`, `random` (for jitter), `typing`,
  `logging`, plus the existing `minecraft_bot` package from 001.
- Test-only: `pytest`, `pytest-asyncio`, `pytest-benchmark` (already
  in dev extras from 001).
- Optional adapter dependencies (out of scope here): `numpy`,
  `gymnasium` would land later behind extras.

**Storage**: in-memory only. No disk persistence for the World cache,
EntityTracker, or InventoryTracker. WireLog capture from 001 is the
only durable artefact, and that's already wired.

**Testing**:
- Python: `pytest -q` for unit tests; `pytest -m live` for live-server
  integration tests; `pytest -q tests/python/perf` for SC-009 latency
  budget verification.
- The physics tick is testable offline: developer (and our tests) call
  `await bot.tick()` directly without the auto-ticker — produces
  deterministic stepping for SC verification.
- A* pathfinder is testable with synthetic World instances (no live
  server needed) — pure-function over a voxel grid.

**Target Platform**: same as 001. Linux/macOS/Windows + WSL2; Python
3.11+; Paper 1.20.1 at `172.26.160.1:25565` for live tests.

**Project Type**: Library / framework — additive on top of 001. No
new top-level project; new files land under `python/minecraft_bot/`
(bot.py, world/, entities/, inventory/, physics.py, pathfinding.py,
behaviour/, events.py, slots.py) and `protocol-data/v763/` (block
states, entity metadata schemas, food table).

**Performance Goals** (per spec SCs):
- Physics tick: ≤ **5 ms median, ≤ 25 ms p99** on commodity hardware
  (SC-009 — identical to 001's decode-and-dispatch budget).
- `walk_to(target 100 blocks, flat)`: arrives within **30 s** (SC-001).
- `walk_to(50 blocks, mixed terrain)`: arrives within **60 s** (SC-002).
- `world.find_blocks_nearby(name, radius=32, limit=5)`: returns in
  **< 100 ms** with chunks loaded (SC-008).
- World cache update on `block_change`: reflected in `get_block` within
  **one server tick (50 ms)** (SC-003).
- Entity tracker position update: same one-tick budget (SC-004).
- Behaviour-tree evaluation (10 nodes, depth 4): **< 1 ms median**
  (SC-010).

**Constraints**:
- Zero runtime deps in core (Constitution VI) — covered by lint test
  inherited from 001 (`tests/python/unit/test_zero_deps.py`).
- Single-bot scope per process; architecture stays multi-bot-ready
  (per-Bot state, no shared mutable globals — FR-131 / Constitution
  via 001's FR-017a).
- 3-slot concurrency model (FR-027): movement / action / container.
  Each slot serialised via `asyncio.Lock`; contending calls raise
  `BotBusy` unless `wait_for_slot=True`.
- Server-driven world cache eviction only (FR-046).
- Physics auto-ticker is best-effort; `await bot.tick()` is the
  manual-stepping entry point for deterministic offline use (FR-010).
- Full entity metadata coverage for ~50 entity types via per-type
  Python subclass (FR-053, FR-056).
- Built strictly on the public `Connection` from 001 — no bypassing
  the framer, registry, or write lock (FR-130).

**Scale/Scope**:
- 134 functional requirements across 12 grouped concerns (bot
  lifecycle, physics, movement APIs, pathfinding, world cache, entity
  tracker, inventory, containers, survival, events, chat, behaviour
  trees, architecture invariants).
- ~50 entity types → ~50 subclass files in
  `protocol/v763/entities/`, scaffolded via codegen from
  `protocol-data/v763/entity_metadata.json`.
- 1 chunk decoder (the big remaining unstructured packet from 001;
  ~600 lines including paletted-container decoding).
- ~700+ typed entity-metadata accessors total (estimated 5-15 per
  type × ~50 types).
- ~750 block types × ~21000 block states in the v763 block-state ID
  table; the cache needs only the ID → name + properties table from
  minecraft-data (no behaviour data).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reviewing the seven principles from `.specify/memory/constitution.md` v1.0.0.

### Initial gate (pre-Phase 0)

| # | Principle | How this plan complies | Verdict |
|---|---|---|---|
| I | Python Is the Source of Truth | Bot lands in Python first; the Rust mirror (in a later milestone) will mirror these classes one-for-one. The public surface defined here is what Rust must reproduce. | ✅ |
| II | One Packet, One File; Versions in Folders | This milestone does not add new packets (all of v763 already shipped in 001). It does add **one file per entity type** under `protocol/v763/entities/` — same Constitution II spirit applied at the entity level. Block-state / entity-metadata data tables under `protocol-data/v763/`. | ✅ |
| III | PyTorch-Style Composable API | Bot mirrors `nn.Module`: state-bearing container with composable submodules (`bot.world`, `bot.entities`, `bot.inventory`, `bot.behaviour`); hooks registered via `@bot.on(EventType)` mirror `register_forward_hook`. Behaviour trees compose like `Sequential`. | ✅ |
| IV | Bots Are Packet Sets | Every Bot state field is derived from inbound packets; the only "client-side fabrication" is the physics-tick local prediction, which is reset to the server's authoritative value on `SynchronizePlayerPosition` (FR-011). No invented state. | ✅ |
| V | Live-Server Integration Testing (NON-NEGOTIABLE) | All P1 user stories ship with live-server integration tests; the P1 smoke suite (US1+US2+US3) MUST pass on Paper 1.20.1 before merge (FR-141). | ✅ |
| VI | Zero Runtime Dependencies in the Core | The Bot, trackers, physics, pathfinder, and behaviour tree all use only stdlib. The existing zero-deps lint from 001 (`tests/python/unit/test_zero_deps.py`) extends to cover the new files automatically. | ✅ |
| VII | Observability and Determinism | Every state change emits a typed event (FR-101) that fires hooks; the WireLog from 001 still captures everything; deterministic offline stepping via `await bot.tick()` (FR-010). | ✅ |

**Initial gate: ✅ passes for all seven.** No Complexity Tracking entries needed.

### Post-Phase 1 re-check

After producing data-model, contracts, and quickstart:

| # | Principle | Re-check note | Verdict |
|---|---|---|---|
| I | Python Is the Source of Truth | `contracts/bot-api.md` is the normative Python surface; Rust mirror in 003 will trace it. | ✅ |
| II | One Packet, One File | `data-model.md` lists one file per entity type; chunk decoder lives in its own module under `world/`; no monolithic packet files. | ✅ |
| III | PyTorch-Style Composable API | `contracts/bot-api.md` exposes `Bot`, `Bot.world`, `Bot.entities`, `Bot.inventory`, `Bot.behaviour` as composable submodules. Hooks via `@bot.on(EventType)`. | ✅ |
| IV | Bots Are Packet Sets | All state derivations in `data-model.md` trace back to inbound packets; `PhysicsState.local_position` is explicitly marked as "predicted; reset on SyncPosition". | ✅ |
| V | Live-Server Integration Testing | `quickstart.md` walks US1+US2+US3 end-to-end live. | ✅ |
| VI | Zero Runtime Dependencies | No new dependency introduced. | ✅ |
| VII | Observability and Determinism | Events listed in `data-model.md`; deterministic `bot.tick()` documented. | ✅ |

**Post-design gate: ✅ passes for all seven.** Plan ready for `/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/002-bot-api/
├── plan.md              # This file (/speckit-plan)
├── research.md          # Phase 0 output (/speckit-plan)
├── data-model.md        # Phase 1 output (/speckit-plan)
├── quickstart.md        # Phase 1 output (/speckit-plan)
├── contracts/
│   └── bot-api.md       # Phase 1 — canonical Bot public API contract
├── checklists/
│   └── requirements.md  # already created in /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
MinecraftBot/
├── python/
│   └── minecraft_bot/
│       │  (existing from 001)
│       ├── connection.py
│       ├── framer.py
│       ├── errors.py
│       ├── wire_log.py
│       ├── codec/                  # 10 primitive codecs
│       ├── protocol/v763/...       # 176 packet files
│       │
│       │  (new in 002)
│       ├── bot.py                  # Bot class — the centerpiece
│       ├── slots.py                # BotBusy + slot model helpers
│       ├── events.py               # Typed Event hierarchy (FR-101)
│       ├── physics.py              # 20-Hz tick + collision/gravity/water
│       ├── pathfinding.py          # 8-dir A* with octile heuristic
│       ├── world/                  # Voxel cache
│       │   ├── __init__.py
│       │   ├── chunk.py            # Chunk + ChunkSection + PalettedContainer
│       │   ├── decode_chunk.py     # Structured map_chunk decoder
│       │   ├── cache.py            # World class
│       │   └── block_table.py      # Block-state ID → name + properties
│       ├── entities/               # Entity tracker + per-type subclasses
│       │   ├── __init__.py
│       │   ├── tracker.py          # EntityTracker
│       │   ├── base.py             # Entity + Living + Mob + Player + Item base classes
│       │   ├── metadata.py         # Entity-metadata stream codec (replaces 001 opaque)
│       │   └── types/              # One file per entity type
│       │       ├── __init__.py     # type-id → class lookup
│       │       ├── sheep.py
│       │       ├── wolf.py
│       │       ├── horse.py
│       │       ├── creeper.py
│       │       ├── villager.py
│       │       ├── ... (~50 files total, codegen-scaffolded then hand-tuned)
│       ├── inventory/              # Inventory + container tracker
│       │   ├── __init__.py
│       │   ├── tracker.py          # InventoryTracker
│       │   ├── item.py             # ItemSlot with NBT-parsed helpers
│       │   ├── food.py             # Food table + BEST_SATURATION/WORST_FIRST/OLDEST_FIRST pickers
│       │   └── window.py           # Window-click protocol helpers
│       └── behaviour/              # Behaviour tree (optional submodule)
│           ├── __init__.py
│           ├── nodes.py            # Selector / Sequence / decorators
│           └── actions.py          # WalkTo / AttackNearest / EatWhenHungry / FollowPlayer
│
├── protocol-data/v763/
│   │  (existing from 001)
│   ├── packet_registry.json
│   ├── golden_bytes/...
│   │
│   │  (new in 002)
│   ├── block_states.json           # Block-state ID -> name + properties
│   ├── entity_metadata.json        # Per-entity-type metadata schemas
│   ├── foods.json                  # Food table (item_id -> food_points + saturation)
│   └── entity_hitboxes.json        # Per-entity-type AABB hitboxes for physics
│
├── tests/
│   ├── python/
│   │   ├── unit/
│   │   │   │  (existing 001 tests)
│   │   │   ├── test_codec_*.py
│   │   │   ├── test_framer.py
│   │   │   ├── ...
│   │   │   │
│   │   │   │  (new in 002)
│   │   │   ├── test_chunk_decode.py        # paletted container parsing
│   │   │   ├── test_world_cache.py         # get_block / find_blocks_nearby
│   │   │   ├── test_pathfinding.py         # offline A* with synthetic World
│   │   │   ├── test_physics.py             # offline tick deterministic stepping
│   │   │   ├── test_entity_metadata.py     # stream codec round-trip
│   │   │   ├── test_entity_subclass_shape.py  # lint: each ~50 subclass has typed accessors
│   │   │   ├── test_inventory_click.py     # window_click translation
│   │   │   ├── test_food_picker.py         # BEST_SATURATION/WORST_FIRST/OLDEST_FIRST
│   │   │   ├── test_slot_model.py          # BotBusy + 3-slot semantics
│   │   │   └── test_behaviour_nodes.py     # Selector / Sequence / decorators
│   │   ├── integration/
│   │   │   │  (existing 001)
│   │   │   ├── test_us1_connect.py
│   │   │   ├── test_us2_decode.py
│   │   │   ├── test_us3_send.py
│   │   │   ├── test_us4_capture_replay_parity.py
│   │   │   ├── test_multi_bot_smoke.py
│   │   │   │
│   │   │   │  (new in 002)
│   │   │   ├── test_us1_walk_to.py         # walk_to flat + mixed terrain (SC-001/002)
│   │   │   ├── test_us2_world_entities.py  # world cache + entity tracker accuracy
│   │   │   ├── test_us3_inventory.py       # open_chest + move_item + craft
│   │   │   ├── test_us4_survive.py         # auto_eat + dig + attack (SC-006/007)
│   │   │   ├── test_us5_follow.py
│   │   │   ├── test_us6_behaviour.py
│   │   │   └── test_us7_chat.py
│   │   ├── perf/
│   │   │   │  (new in 002)
│   │   │   ├── test_tick_latency.py        # SC-009: physics tick <5ms median
│   │   │   ├── test_find_blocks.py         # SC-008: find_blocks_nearby <100ms
│   │   │   └── test_behaviour_eval.py      # SC-010: 10-node tree <1ms
│   │   └── replay/  (existing 001)
│
└── tools/                          # not shipped; helper scripts
    ├── (existing 001)
    ├── generate_packet_skeletons.py
    ├── cross_check.py
    ├── capture_session.py
    │
    │  (new in 002)
    ├── generate_entity_subclasses.py   # entity_metadata.json -> ~50 subclass scaffolds
    ├── fetch_block_states.py            # pull block_states.json from minecraft-data
    └── fetch_foods.py                   # pull foods.json from minecraft-data
```

**Structure Decision**: Bot API is purely additive on top of 001 —
same monorepo, same `minecraft_bot` package; new submodules slot in
beside the existing `codec/`, `protocol/v763/`, `connection.py`, etc.
Entity tracker uses one-file-per-type under `entities/types/` (echoes
the per-packet structure from Constitution II). Per-version data
tables (block states, entity metadata, foods) live under
`protocol-data/v763/` alongside the existing `packet_registry.json`.
The structure scales naturally to 1.20.2+ later: new entity types
under `entities/types/`, new data tables under `protocol-data/v764/`.

## Complexity Tracking

> No constitution violations. Section intentionally empty.
