# Implementation Plan: Full Bot Parity Across Three Backends

**Branch**: `004-full-bot-parity` | **Date**: 2026-05-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-full-bot-parity/spec.md`

## Summary

Port the entire Python `Bot` public surface (~60 methods across `bot.py`, `dig.py`, `behaviour/`, `observation.py`, `inventory/`, `foods.py`) to the standalone Rust crate (`rust/`) and re-export through the PyO3 facade (`python-ext/`) so that `minecraft_bot`, the Rust `minecraft_bot` crate, and `minecraft_bot_accel` expose the **same** Bot API. Python remains the spec of record.

The work splits into eight sequential method groups (state accessors -> movement -> combat -> world query -> observation -> inventory -> containers -> high-level tasks -> behaviour trees) plus parity-test infrastructure and a 0.3.0 release. Each group is shipped as one commit: implement Rust, wrap accel, write parity test, live-test on Paper 1.20.1, commit. The hard gate is the introspection test (`tests/python/parity/test_bot_full_parity.py`) — once green, the README claim "all three artefacts share the same Bot surface" becomes enforceable.

## Technical Context

**Language/Version**: Python 3.11+ (reference), Rust 1.75+ (standalone crate + PyO3 facade)
**Primary Dependencies**: tokio 1.x, pyo3 0.22 (abi3-py311), pyo3-async-runtimes 0.22 (tokio feature), parking_lot 0.12, serde_json 1, async-trait 0.1, maturin 1.13.3
**Storage**: N/A (live network protocol, in-memory state)
**Testing**: pytest + pytest-asyncio (parity, integration, perf), cargo test (Rust unit + `--features live-smoke` integration), introspection-based method enumeration
**Target Platform**: Linux x86_64/aarch64, Windows x86_64 wheels; macOS via pure-Python wheel + local maturin; Rust crate any platform with stable rustc
**Project Type**: Three-artefact monorepo (Python ref + Rust crate + PyO3 facade). Layout established in 003.
**Performance Goals**: Existing perf gates from 003 hold (chunk decode 31x, batched VarInt 25x, A* 6x). New gates: >=3x speedup on `find_blocks_nearby` / `raycast` / `scan_volume` for accel vs Python.
**Constraints**: Constitution VI (zero runtime deps in Python core), Constitution V (live test on Paper 1.20.1 mandatory), Constitution I (Python is the source of truth — Rust chases Python, never reverse). Pure-Rust crate must compile without pyo3.
**Scale/Scope**: ~60 Bot methods x 3 backends + ~50 new parity tests + ~12 live-smoke Rust integration tests + behaviour-tree module (Selector/Sequencer/Inverter/Repeater + 4 standard leaves) + dual-list InventoryState + foods table + recipe loader. Estimated 3000 LOC new Rust, 1500 LOC new accel, 1500 LOC new tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Python Is the Source of Truth | PASS | Spec explicitly names Python as canonical; all 5 clarifications defer to Python reference (Q1 accessor style, Q2 craft sig, Q3 BT leaf sig, Q5 inventory model). |
| II. One Packet, One File; Versions in Folders | PASS | 004 adds no new packets. Reuses existing 176 packets per v763 already in the per-file layout. |
| III. PyTorch-Style Composable API | PASS | Behaviour trees are the canonical composable unit (Selector/Sequencer/Leaf). Snapshot/observation values are frozen. The Python ref uses flat method names on Bot rather than sub-modules; we follow Python here. |
| IV. Bots Are Packet Sets, Not Entities | PASS | Bot stays a method-bag over a Connection. No new entity hierarchy. |
| V. Live-Server Integration Testing | PASS | FR-048 requires `cargo test --features live-smoke`; FR-047 requires packet-trace parity (presupposes live capture). Live tests on Paper 1.20.1 are part of every method's acceptance. |
| VI. Zero Runtime Dependencies in the Core | PASS | Python core unchanged. Pure-Rust crate adds zero new runtime deps. `BehaviourValue` is a closed enum; no pyo3 in pure-Rust. `async-trait` is the one candidate addition — if rejected, the trait can be expressed manually via `Pin<Box<dyn Future + Send>>` returns. |
| VII. Observability and Determinism | PASS | Parity test framework forces packet-trace logging via WireLog. Tolerance whitelist (Q4) is field-scoped — determinism not weakened. |

**Result**: All gates pass. No complexity-tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/004-full-bot-parity/
├── plan.md                       # This file
├── spec.md                       # User-facing spec with clarifications
├── research.md                   # Phase 0 output (technical decisions)
├── data-model.md                 # Phase 1 output (entity definitions)
├── quickstart.md                 # Phase 1 output (dev workflow)
├── contracts/
│   └── api-surface.md            # Phase 1 output (method-by-method contract)
├── checklists/
│   └── requirements.md           # Spec quality checklist (from /speckit-specify)
└── tasks.md                      # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
python/minecraft_bot/              # Python reference — read-only for 004
├── bot.py                         # ~60 methods, already complete
├── dig.py
├── behaviour/                     # Selector / Sequencer / Inverter / Repeater / nodes
├── observation.py
├── inventory/                     # tracker.py, click.py, item.py
├── foods.py
└── ...

rust/src/                          # Standalone Rust crate — major expansion in 004
├── bot/
│   ├── mod.rs                     # Bot struct + state, re-exports
│   ├── state.rs                   # BotState fields, accessor methods (~17 methods)
│   ├── movement.rs                # look_at, jump, sneak, sprint, swing_arm
│   ├── combat.rs                  # attack, interact_entity, use_item
│   ├── world_query.rs             # find_blocks_nearby, raycast, scan_volume,
│   │                              #   voxel_grid, chunks_around, world_map_3d,
│   │                              #   nearby_entities, nearby_players, distance_to
│   ├── inventory.rs               # InventoryState (dual-list), held_item,
│   │                              #   find_item, count_item, select_slot,
│   │                              #   drop_item, click_slot, move_item,
│   │                              #   quick_move, equip_armor, unequip_armor,
│   │                              #   swap_to_offhand, iter_accessible_slots
│   ├── containers.rs              # open_block_container, open_chest,
│   │                              #   open_furnace, open_crafting_table,
│   │                              #   close_container, craft
│   ├── tasks.rs                   # dig, eat, follow, say, chat
│   ├── walk_to.rs                 # (already exists from 003)
│   └── packet_hooks.rs            # (already exists from 003)
├── behaviour/
│   ├── mod.rs                     # Selector, Sequencer, Inverter, Repeater,
│   │                              #   BehaviourRunner, NodeStatus, BehaviourCtx,
│   │                              #   BehaviourValue
│   ├── leaf.rs                    # Leaf trait
│   └── leaves/
│       ├── walk_to.rs
│       ├── eat_when_hungry.rs
│       ├── follow_entity.rs
│       └── attack_target.rs
├── observation.rs                 # (extend existing) snapshot, observation
├── foods.rs                       # NEW: food-id -> (hunger, saturation) table
├── recipes.rs                     # NEW: load protocol-data/v763/recipes.json
└── inventory/                     # NEW: item.rs (ItemSlot), tracker logic
    ├── mod.rs
    ├── item.rs
    └── click.rs                   # click_slot sequence helpers, move_item algorithm

python-ext/src/                    # PyO3 facade — wrap every new Rust method
├── bot/
│   ├── mod.rs                     # Re-exports + Bot #[pyclass]
│   ├── state_getters.rs           # #[getter] for each accessor (sync properties)
│   ├── movement_py.rs             # look_at, jump, sneak, sprint, swing_arm
│   ├── combat_py.rs               # attack, interact_entity, use_item
│   ├── world_query_py.rs          # find_blocks_nearby, raycast, etc.
│   ├── inventory_py.rs            # all inventory methods, ItemSlot pyclass
│   ├── containers_py.rs           # open_*, close_container, craft
│   └── tasks_py.rs                # dig, eat, follow, say
├── behaviour_py.rs                # NEW: Selector/Sequencer pyclass,
│                                  #   PyLeaf wrapper for Python objects,
│                                  #   BehaviourCtx <-> Python dict conversion
└── foods_py.rs                    # NEW: expose food table to Python

tests/
├── python/
│   ├── parity/
│   │   ├── test_bot_full_parity.py      # NEW: introspection — same method set
│   │   ├── test_method_signatures.py    # NEW: signature shape comparison
│   │   ├── test_packet_trace_parity.py  # NEW: per-method packet trace diff
│   │   ├── _parity_normalizer.py        # NEW: whitelist of tolerant fields
│   │   └── ...
│   ├── integration/                     # Live tests (Paper 1.20.1)
│   │   ├── test_bot_full_parity_live.py # NEW: every method end-to-end
│   │   └── ...
│   └── perf/
│       └── test_speedup_world_query.py  # NEW: find_blocks_nearby, raycast,
│                                        #   scan_volume >=3x
├── rust/
│   └── integration_bot_full.rs          # NEW: cargo test --features live-smoke
└── ...

protocol-data/v763/
├── block_states.json                    # already exists, dig hardness source
├── items.json                           # already exists, find_item source
└── recipes.json                         # already exists, craft source
```

**Structure Decision**: Reuse the three-artefact layout from 003. 004 splits `rust/src/bot.rs` (currently single file with 13 methods) into `rust/src/bot/{state, movement, combat, world_query, inventory, containers, tasks, walk_to, packet_hooks}.rs` to keep each file under ~400 lines. Same mirror in `python-ext/src/bot/`. New top-level modules: `rust/src/behaviour/`, `rust/src/foods.rs`, `rust/src/recipes.rs`, `rust/src/inventory/`. The `python/` tree is read-only for 004 (Python is the spec).

## Complexity Tracking

No constitution violations. No complexity-tracking entries needed.
